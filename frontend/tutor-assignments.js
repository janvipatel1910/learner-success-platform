"use strict";

// Tutor panel: read learners' assignment answers, then approve them or ask
// for changes with feedback. Tutors only.
(() => {
  const base = `/catalog/courses/${pilotContext.courseId}` +
    `/cohorts/${pilotContext.cohortId}/assignment-submissions`;
  const headers = { "X-Organization-ID": pilotContext.organizationId };
  const jsonHeaders = { ...headers, "Content-Type": "application/json" };

  const FILTERS = [
    ["submitted", "Waiting for review"],
    ["changes_requested", "Changes requested"],
    ["approved", "Approved"],
    ["", "All answers"]
  ];
  const STATUS_LABEL = {
    submitted: "Waiting for review",
    changes_requested: "Changes requested",
    approved: "Approved"
  };

  function note(text) {
    const node = element("p", "notice", text);
    node.setAttribute("role", "status");
    return node;
  }

  function safeLink(href) {
    try {
      const url = new URL(href);
      if (url.protocol !== "https:" || url.username || url.password) return null;
      const link = element("a", "", "Open learner's link");
      link.href = url.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      return link;
    } catch {
      return null;
    }
  }

  function reviewForm(item, reload) {
    const form = document.createElement("form");
    form.className = "assignment-review";

    const id = `feedback-${item.submission_id}`;
    const label = element("label", "", "Feedback for the learner");
    label.htmlFor = id;
    const feedback = document.createElement("textarea");
    feedback.id = id;
    feedback.rows = 4;
    feedback.required = true;
    feedback.minLength = 10;
    feedback.maxLength = 5000;
    feedback.placeholder = "For example: Good use of two AZs. Please add the database security group rule.";

    const approve = element("button", "", "Approve");
    approve.type = "submit";
    approve.value = "approved";
    const changes = element("button", "", "Ask for changes");
    changes.type = "submit";
    changes.value = "changes_requested";
    const result = note("");
    result.hidden = true;

    form.append(label, feedback, approve, changes, result);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const decision = event.submitter?.value;
      result.hidden = false;
      if (!decision) return;
      if (feedback.value.trim().length < 10) {
        result.textContent = "Write at least 10 characters of feedback.";
        feedback.focus();
        return;
      }

      approve.disabled = changes.disabled = feedback.disabled = true;
      result.textContent = "Saving review…";
      try {
        await window.skillpulseAuth.request(
          `${base}/${item.submission_id}/review`,
          {
            method: "PUT",
            headers: jsonHeaders,
            body: JSON.stringify({
              review_status: decision,
              tutor_feedback: feedback.value.trim()
            })
          }
        );
        await reload(
          decision === "approved"
            ? `Approved ${item.learner_name}'s answer.`
            : `Sent ${item.learner_name}'s answer back for changes.`
        );
      } catch (error) {
        approve.disabled = changes.disabled = feedback.disabled = false;
        result.textContent = `Could not save the review: ${error.message}`;
      }
    });

    return form;
  }

  function renderCard(item, reload) {
    const card = element("article", "assignment-card");
    card.dataset.status = item.review_status;

    const tags = element("p", "assignment-tags");
    tags.append(
      element("span", "badge", item.module_title),
      element("span", "badge", STATUS_LABEL[item.review_status] || item.review_status)
    );
    if (!item.is_latest) tags.append(element("span", "badge", "Older attempt"));

    const answer = element("p", "", item.answer_text);
    answer.style.whiteSpace = "pre-wrap";

    card.append(
      element("h3", "", `${item.learner_name} · ${item.assignment_title}`),
      tags,
      element(
        "p", "assignment-meta",
        `Attempt ${item.submission_number} · sent ` +
          new Date(item.submitted_at).toLocaleString()
      ),
      answer
    );
    const link = item.link_url && safeLink(item.link_url);
    if (link) card.append(link);

    if (item.tutor_feedback) {
      const feedback = element("p", "", item.tutor_feedback);
      feedback.style.whiteSpace = "pre-wrap";
      card.append(element("h4", "", "Your feedback"), feedback);
    }

    if (item.review_status === "submitted" && item.is_latest) {
      card.append(reviewForm(item, reload));
    }
    return card;
  }

  async function load(list, summary, filter, message = "") {
    list.replaceChildren(note("Loading answers…"));
    const query = new URLSearchParams({ limit: "100", offset: "0" });
    if (filter.value) query.set("review_status", filter.value);
    try {
      const page = await window.skillpulseAuth.request(`${base}?${query}`, { headers });
      const items = Array.isArray(page.items) ? page.items : [];
      const chosen = FILTERS.find(([value]) => value === filter.value)?.[1] || "";

      summary.textContent = filter.value === "submitted"
        ? (items.length
            ? `${items.length} answer${items.length === 1 ? " is" : "s are"} waiting for your review.`
            : "No answers are waiting for review.")
        : `${page.total ?? items.length} answer${items.length === 1 ? "" : "s"} · ${chosen}`;

      const reload = (text) => load(list, summary, filter, text);
      list.replaceChildren();
      if (message) list.append(note(message));
      items.forEach((item) => list.append(renderCard(item, reload)));
    } catch (error) {
      summary.textContent = "";
      list.replaceChildren(note(`Could not load answers: ${error.message}`));
    }
  }

  window.addEventListener("skillpulse:signed-in", (event) => {
    const user = event.detail?.user;
    const isTutor = user?.memberships?.some(
      (membership) =>
        membership.organization_id === pilotContext.organizationId &&
        membership.role === "tutor"
    );
    if (!isTutor || document.getElementById("tutor-assignments")) return;

    const panel = element("section", "card");
    panel.id = "tutor-assignments";
    const summary = element("p", "", "");
    const list = element("div", "assignment-list");

    const filter = document.createElement("select");
    filter.id = "assignment-filter";
    FILTERS.forEach(([value, label]) => {
      const option = element("option", "", label);
      option.value = value;
      filter.append(option);
    });
    const filterLabel = element("label", "", "Show");
    filterLabel.htmlFor = filter.id;
    filterLabel.append(filter);

    const refresh = element("button", "", "Refresh answers");
    refresh.type = "button";

    panel.append(
      element("p", "eyebrow", "ASSIGNMENTS"),
      element("h2", "", "Assignment reviews"),
      element(
        "p", "",
        "Read each answer, then approve it or ask for changes. Feedback is " +
          "shown to the learner. Approved assignments count towards the certificate."
      ),
      summary,
      filterLabel,
      refresh,
      list
    );

    const run = () => load(list, summary, filter);
    filter.addEventListener("change", run);
    refresh.addEventListener("click", run);

    const anchorPanel = document.getElementById("tutor-attendance") ||
      document.getElementById("tutor-blockers") ||
      document.getElementById("tutor-dashboard");
    if (anchorPanel) anchorPanel.after(panel);
    else document.querySelector(".workspace-header")?.after(panel);

    const nav = document.querySelector(".sidebar nav");
    if (nav) {
      const link = element("a", "", "Assignment Reviews");
      link.href = "#tutor-assignments";
      const reviewsLink = nav.querySelector('a[href="#tutor-reviews"]');
      if (reviewsLink) reviewsLink.before(link);
      else nav.append(link);
    }

    run();
  });
})();
