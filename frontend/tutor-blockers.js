"use strict";

// Tutor panel: see learner blockers, take one, record what you did, resolve it.
// Uses the existing blocker and intervention API; tutors only.
(() => {
  const base = `/catalog/courses/${pilotContext.courseId}` +
    `/cohorts/${pilotContext.cohortId}/blockers`;
  const headers = { "X-Organization-ID": pilotContext.organizationId };
  const jsonHeaders = { ...headers, "Content-Type": "application/json" };

  const ACTIVE = new Set(["open", "assigned", "waiting_student"]);
  const STATUS_LABEL = {
    open: "Open",
    assigned: "Assigned",
    waiting_student: "Waiting for learner",
    resolved: "Resolved",
    closed: "Closed"
  };
  const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3 };
  const INTERVENTION_TYPES = [
    "One-to-one explanation",
    "Guided practice",
    "Extra learning resource",
    "Follow-up class",
    "Other"
  ];

  let currentUserId = null;

  function note(text) {
    const node = element("p", "notice", text);
    node.setAttribute("role", "status");
    return node;
  }

  function field(labelText, input) {
    const label = element("label", "", labelText);
    label.append(input);
    return label;
  }

  function textArea(placeholder) {
    const area = document.createElement("textarea");
    area.rows = 3;
    area.required = true;
    area.maxLength = 2000;
    area.placeholder = placeholder;
    return area;
  }

  function sortBlockers(items) {
    return [...items].sort((a, b) =>
      (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9) ||
      new Date(a.opened_at) - new Date(b.opened_at)
    );
  }

  function interventionForm(blocker, onDone) {
    const form = document.createElement("form");
    form.className = "blocker-action";

    const type = document.createElement("select");
    INTERVENTION_TYPES.forEach((label) => {
      const option = element("option", "", label);
      option.value = label;
      type.append(option);
    });
    const action = textArea("For example: Walked through S3 bucket policies with an example.");
    const submit = element("button", "", "Save support given");
    submit.type = "submit";
    const result = note("");
    result.hidden = true;

    form.append(
      field("Support given", type),
      field("What did you do?", action),
      submit,
      result
    );

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!form.reportValidity() || !action.value.trim()) return;
      submit.disabled = true;
      result.hidden = false;
      result.textContent = "Saving…";
      try {
        await window.skillpulseAuth.request(`${base}/${blocker.id}/interventions`, {
          method: "POST",
          headers: jsonHeaders,
          body: JSON.stringify({
            intervention_type: type.value,
            action_taken: action.value.trim()
          })
        });
        result.textContent = "Support recorded.";
        await onDone();
      } catch (error) {
        result.textContent = `Could not save: ${error.message}`;
        submit.disabled = false;
      }
    });

    return form;
  }

  function resolveForm(blocker, onDone) {
    const form = document.createElement("form");
    form.className = "blocker-action";
    const summary = textArea("For example: Learner can now explain bucket policies and passed the quiz.");
    const submit = element("button", "", "Mark as resolved");
    submit.type = "submit";
    const result = note("");
    result.hidden = true;

    form.append(field("How was it resolved?", summary), submit, result);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!form.reportValidity() || !summary.value.trim()) return;
      submit.disabled = true;
      result.hidden = false;
      result.textContent = "Saving…";
      try {
        await window.skillpulseAuth.request(`${base}/${blocker.id}`, {
          method: "PUT",
          headers: jsonHeaders,
          body: JSON.stringify({
            status: "resolved",
            resolution_summary: summary.value.trim()
          })
        });
        await onDone();
      } catch (error) {
        result.textContent = `Could not resolve: ${error.message}`;
        submit.disabled = false;
      }
    });

    return form;
  }

  function renderCard(blocker, reload) {
    const card = element("article", "blocker-card");
    card.dataset.severity = blocker.severity;

    const meta = element(
      "p",
      "blocker-meta",
      `${blocker.learner_full_name} · ${blocker.category} · ` +
        `opened ${new Date(blocker.opened_at).toLocaleDateString()}`
    );
    const tags = element("p", "blocker-tags");
    tags.append(
      element("span", `badge severity-${blocker.severity}`, blocker.severity),
      element("span", "badge", STATUS_LABEL[blocker.status] || blocker.status)
    );
    if (blocker.assigned_tutor_full_name) {
      tags.append(element("span", "badge", `Owner: ${blocker.assigned_tutor_full_name}`));
    }

    card.append(
      element("h3", "", blocker.title),
      tags,
      meta,
      element("p", "", blocker.description)
    );

    if (!ACTIVE.has(blocker.status)) {
      if (blocker.resolution_summary) {
        card.append(element("p", "blocker-meta", `Resolution: ${blocker.resolution_summary}`));
      }
      return card;
    }

    if (blocker.status === "open" && currentUserId) {
      const take = element("button", "", "Take this blocker");
      take.type = "button";
      take.addEventListener("click", async () => {
        take.disabled = true;
        take.textContent = "Assigning…";
        try {
          await window.skillpulseAuth.request(`${base}/${blocker.id}`, {
            method: "PUT",
            headers: jsonHeaders,
            body: JSON.stringify({ status: "assigned", assigned_tutor_id: currentUserId })
          });
          await reload();
        } catch (error) {
          take.textContent = "Take this blocker";
          take.disabled = false;
          card.append(note(`Could not assign: ${error.message}`));
        }
      });
      card.append(take);
    }

    const support = element("details", "topic-details");
    support.append(element("summary", "", "Record support given"), interventionForm(blocker, reload));
    const resolve = element("details", "topic-details");
    resolve.append(element("summary", "", "Resolve"), resolveForm(blocker, reload));
    card.append(support, resolve);

    return card;
  }

  async function load(panel, list, summary) {
    list.replaceChildren(note("Loading learner blockers…"));
    try {
      const page = await window.skillpulseAuth.request(`${base}?limit=100&offset=0`, { headers });
      const items = Array.isArray(page.items) ? page.items : [];
      const active = sortBlockers(items.filter((b) => ACTIVE.has(b.status)));
      const done = items.filter((b) => !ACTIVE.has(b.status));

      summary.textContent = active.length
        ? `${active.length} learner blocker${active.length === 1 ? " needs" : "s need"} attention.`
        : "No learner blockers need attention right now.";

      list.replaceChildren();
      const reload = () => load(panel, list, summary);
      active.forEach((blocker) => list.append(renderCard(blocker, reload)));

      if (done.length) {
        const history = element("details", "topic-details");
        history.append(element("summary", "", `Resolved and closed (${done.length})`));
        done.forEach((blocker) => history.append(renderCard(blocker, reload)));
        list.append(history);
      }
    } catch (error) {
      summary.textContent = "";
      list.replaceChildren(note(`Could not load learner blockers: ${error.message}`));
    }
  }

  window.addEventListener("skillpulse:signed-in", (event) => {
    const user = event.detail?.user;
    const isTutor = user?.memberships?.some(
      (membership) =>
        membership.organization_id === pilotContext.organizationId &&
        membership.role === "tutor"
    );
    if (!isTutor || document.getElementById("tutor-blockers")) return;
    currentUserId = user.user_id;

    const panel = element("section", "card");
    panel.id = "tutor-blockers";
    const summary = element("p", "", "");
    const refresh = element("button", "", "Refresh blockers");
    refresh.type = "button";
    const list = element("div", "blocker-list");
    panel.append(
      element("p", "eyebrow", "LEARNER SUPPORT"),
      element("h2", "", "Learner blockers"),
      summary,
      refresh,
      list
    );
    refresh.addEventListener("click", () => load(panel, list, summary));

    const dashboard = document.getElementById("tutor-dashboard");
    if (dashboard) dashboard.after(panel);
    else document.querySelector(".workspace-header")?.after(panel);

    const nav = document.querySelector(".sidebar nav");
    if (nav) {
      const link = element("a", "", "Learner Blockers");
      link.href = "#tutor-blockers";
      const reviewsLink = nav.querySelector('a[href="#tutor-reviews"]');
      if (reviewsLink) reviewsLink.before(link);
      else nav.append(link);
    }

    load(panel, list, summary);
  });
})();
