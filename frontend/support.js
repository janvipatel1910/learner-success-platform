"use strict";

(() => {
  const section = document.getElementById("support");
  const headers = {
    "X-Organization-ID": pilotContext.organizationId
  };
  const cohortBase =
    `/catalog/courses/${pilotContext.courseId}` +
    `/cohorts/${pilotContext.cohortId}`;
  const activeStatuses = new Set(["open", "assigned", "waiting_student"]);
  const statusLabels = {
    open: "Open",
    assigned: "Assigned",
    waiting_student: "Waiting for learner",
    resolved: "Resolved",
    closed: "Closed"
  };

  section.replaceChildren(
    element("p", "eyebrow", "ASK FOR HELP"),
    element("h2", "", "Learning support"),
    element("p", "", "Describe what is stopping your progress.")
  );

  const message = element("p", "form-note", "Sign in to load your blockers.");
  message.setAttribute("role", "status");

  const refresh = element("button", "", "Refresh blockers");
  refresh.type = "button";
  refresh.disabled = true;

  const list = element("div", "learning-path");
  const form = element("form", "");
  const fieldset = element("fieldset", "");
  fieldset.disabled = true;
  fieldset.append(element("legend", "", "Report a learning blocker"));

  function addField(labelText, id, control) {
    const label = element("label", "", labelText);
    label.htmlFor = id;
    control.id = id;
    fieldset.append(label, control);
    return control;
  }

  const title = addField(
    "Short title", "blocker-title", element("textarea", "")
  );
  title.rows = 2;
  title.required = true;
  title.maxLength = 200;

  const description = addField(
    "What have you tried, and where are you stuck?",
    "blocker-description",
    element("textarea", "")
  );
  description.rows = 4;
  description.required = true;
  description.maxLength = 5000;

  const category = addField(
    "Category", "blocker-category", element("select", "")
  );
  for (const value of ["Concept", "Lab", "Assessment", "Access", "Other"]) {
    category.append(new Option(value, value.toLowerCase()));
  }

  const severity = addField(
    "Impact", "blocker-severity", element("select", "")
  );
  for (const [value, label] of [
    ["low", "Low — minor difficulty"],
    ["medium", "Medium — need some help"],
    ["high", "High — blocking progress"],
    ["critical", "Critical — cannot continue"]
  ]) {
    severity.append(new Option(label, value));
  }
  severity.value = "medium";

  const save = element("button", "", "Submit blocker");
  save.type = "submit";
  fieldset.append(save);
  form.append(fieldset);

  const saveMessage = element("p", "form-note", "");
  saveMessage.setAttribute("role", "status");

  section.append(message, refresh, list, form, saveMessage);

  function renderBlockers(blockers) {
    list.replaceChildren();

    const active = blockers.filter((blocker) =>
      activeStatuses.has(blocker.status)
    );
    setText("blockers-summary", String(active.length));

    if (!blockers.length) {
      list.append(element("p", "empty-state", "No blockers reported for this cohort."));
      return;
    }

    for (const blocker of blockers) {
      const card = element("details", "empty-state");
      card.style.overflowWrap = "anywhere";
      card.append(
        element("summary", "", blocker.title),
        element("p", "",
          `${statusLabels[blocker.status] || blocker.status} · ${blocker.severity}`),
        element("p", "", blocker.description),
        element("p", "",
          `Tutor: ${blocker.assigned_tutor_full_name || "Not assigned yet"}`)
      );

      if (blocker.resolution_summary) {
        card.append(
          element("strong", "", "Resolution"),
          element("p", "", blocker.resolution_summary)
        );
      }
      list.append(card);
    }
  }

  async function loadBlockers() {
    refresh.disabled = true;
    message.textContent = "Loading blockers…";

    try {
      const blockers = [];
      let offset = 0;

      while (true) {
        const page = await window.skillpulseAuth.request(
          `/catalog/my-blockers?limit=100&offset=${offset}`,
          { headers }
        );

        if (!Array.isArray(page.items)) {
          throw new Error("Unexpected blocker response.");
        }

        blockers.push(...page.items);
        offset += page.items.length;
        if (offset >= page.total || page.items.length === 0) break;
      }

      const scoped = blockers.filter((blocker) =>
        blocker.course_id === pilotContext.courseId &&
        blocker.cohort_id === pilotContext.cohortId
      );

      renderBlockers(scoped);
      message.textContent =
        "Loaded this cohort's blockers. Open count includes open, assigned and waiting-for-learner records.";
    } catch (error) {
      setText("blockers-summary", "—");
      list.replaceChildren();
      message.textContent = `Could not load blockers. ${error.message}`;
    } finally {
      refresh.disabled = false;
    }
  }

  refresh.addEventListener("click", loadBlockers);

  window.addEventListener("skillpulse:signed-in", () => {
    fieldset.disabled = false;
    loadBlockers();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (fieldset.disabled || !form.reportValidity()) return;

    const payload = {
      title: title.value.trim(),
      description: description.value.trim(),
      category: category.value,
      severity: severity.value,
      topic_id: null
    };

    if (!payload.title || !payload.description) {
      saveMessage.textContent = "Enter a title and description, not just spaces.";
      return;
    }

    fieldset.disabled = true;
    saveMessage.textContent = "Submitting blocker…";

    try {
      await window.skillpulseAuth.request(`${cohortBase}/my-blockers`, {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    } catch (error) {
      saveMessage.textContent =
        `Submission could not be confirmed. ${error.message} ` +
        "Refresh the blocker list before retrying to avoid a duplicate.";
      fieldset.disabled = false;
      return;
    }

    form.reset();
    severity.value = "medium";
    saveMessage.textContent = "Blocker submitted successfully.";
    fieldset.disabled = false;
    await loadBlockers();

    // New unresolved blockers can affect the current readiness score.
    try {
      const readiness = await window.skillpulseAuth.request(
        `${cohortBase}/readiness/me`, { headers }
      );
      renderReadiness(readiness);
    } catch (error) {
      setText("overall-score", "—");
      setText("readiness-level", "Refresh needed");
      setText("readiness-summary",
        "Blocker saved, but readiness could not be refreshed. Sign in again to reload.");
    }
  });
})();
