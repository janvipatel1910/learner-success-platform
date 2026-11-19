"use strict";

// Tutor panel: add classes, mark them as completed and take attendance.
// Attendance can only be recorded for completed classes, and it counts
// towards each learner's exam readiness. Uses the existing session and
// attendance API; tutors only.
(() => {
  const base = `/catalog/courses/${pilotContext.courseId}` +
    `/cohorts/${pilotContext.cohortId}/sessions`;
  const headers = { "X-Organization-ID": pilotContext.organizationId };
  const jsonHeaders = { ...headers, "Content-Type": "application/json" };

  const STATUS_LABEL = {
    scheduled: "Scheduled",
    completed: "Completed",
    cancelled: "Cancelled"
  };
  const ATTENDANCE_OPTIONS = [
    ["", "Not recorded"],
    ["present", "Present"],
    ["late", "Late"],
    ["absent", "Absent"],
    ["excused", "Excused"]
  ];

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

  function input(type, required = true) {
    const node = document.createElement("input");
    node.type = type;
    node.required = required;
    return node;
  }

  // Value for a datetime-local input, in the tutor's own time zone.
  function localValue(date) {
    const copy = new Date(date);
    copy.setMinutes(copy.getMinutes() - copy.getTimezoneOffset());
    return copy.toISOString().slice(0, 16);
  }

  function durationMinutes(session) {
    return Math.ceil(
      (new Date(session.scheduled_end) - new Date(session.scheduled_start)) / 60000
    );
  }

  function when(session) {
    const start = new Date(session.scheduled_start);
    const end = new Date(session.scheduled_end);
    return `${start.toLocaleDateString()} · ` +
      `${start.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}–` +
      `${end.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
  }

  function moduleTitle(topicId) {
    return courseContent[topicId]?.title || "Module";
  }

  function addClassForm(onDone) {
    const form = document.createElement("form");
    form.className = "attendance-form";

    const topic = document.createElement("select");
    topic.required = true;
    Object.entries(courseContent).forEach(([id, content]) => {
      const option = element("option", "", content.title);
      option.value = id;
      topic.append(option);
    });

    const title = input("text");
    title.maxLength = 200;
    title.placeholder = "For example: VPC routing workshop";

    // Default: a one-hour class that started an hour ago, so a class that has
    // just happened can be added and its attendance taken straight away.
    const start = input("datetime-local");
    start.value = localValue(Date.now() - 60 * 60 * 1000);
    const end = input("datetime-local");
    end.value = localValue(Date.now());

    const link = input("url", false);
    link.placeholder = "https://...";

    const submit = element("button", "", "Add class");
    submit.type = "submit";
    const result = note("");
    result.hidden = true;

    form.append(
      field("Module", topic),
      field("Class title", title),
      field("Start date and time", start),
      field("End date and time", end),
      field("Class link (optional)", link),
      submit,
      result
    );

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;

      const startDate = new Date(start.value);
      const endDate = new Date(end.value);
      result.hidden = false;
      if (endDate <= startDate) {
        result.textContent = "The end time must be after the start time.";
        return;
      }

      submit.disabled = true;
      result.textContent = "Adding class…";
      try {
        await window.skillpulseAuth.request(base, {
          method: "POST",
          headers: jsonHeaders,
          body: JSON.stringify({
            topic_id: topic.value,
            title: title.value.trim(),
            scheduled_start: startDate.toISOString(),
            scheduled_end: endDate.toISOString(),
            delivery_link: link.value.trim() || null
          })
        });
        result.textContent = "Class added.";
        title.value = "";
        link.value = "";
        await onDone();
      } catch (error) {
        result.textContent = `Could not add the class: ${error.message}`;
      } finally {
        submit.disabled = false;
      }
    });

    return form;
  }

  async function markCompleted(session, button, card, reload) {
    button.disabled = true;
    button.textContent = "Saving…";
    try {
      // The API replaces the whole class record, so send every field back.
      await window.skillpulseAuth.request(`${base}/${session.id}`, {
        method: "PUT",
        headers: jsonHeaders,
        body: JSON.stringify({
          topic_id: session.topic_id,
          title: session.title,
          scheduled_start: session.scheduled_start,
          scheduled_end: session.scheduled_end,
          delivery_link: session.delivery_link,
          recording_url: session.recording_url,
          status: "completed"
        })
      });
      await reload(session.id);
    } catch (error) {
      button.disabled = false;
      button.textContent = "Mark as completed";
      card.append(note(`Could not update the class: ${error.message}`));
    }
  }

  async function loadRoster(session, target, message = "") {
    target.replaceChildren(note("Loading learners…"));
    try {
      const page = await window.skillpulseAuth.request(
        `${base}/${session.id}/attendance?limit=100&offset=0`,
        { headers }
      );
      const items = Array.isArray(page.items) ? page.items : [];
      if (!items.length) {
        target.replaceChildren(note("No learners are enrolled in this cohort yet."));
        return;
      }
      const form = rosterForm(
        session, items, (text) => loadRoster(session, target, text)
      );
      target.replaceChildren(form);
      if (message) target.prepend(note(message));
    } catch (error) {
      target.replaceChildren(note(`Could not load learners: ${error.message}`));
    }
  }

  function rosterForm(session, items, reload) {
    const form = document.createElement("form");
    const maxMinutes = durationMinutes(session);
    const rows = [];

    const table = document.createElement("table");
    const headRow = document.createElement("tr");
    ["Learner", "Attendance", `Minutes (optional, up to ${maxMinutes})`].forEach(
      (label) => headRow.append(element("th", "", label))
    );
    const head = document.createElement("thead");
    head.append(headRow);
    const body = document.createElement("tbody");

    items.forEach((item) => {
      const status = document.createElement("select");
      status.setAttribute("aria-label", `Attendance for ${item.full_name}`);
      ATTENDANCE_OPTIONS.forEach(([value, label]) => {
        const option = element("option", "", label);
        option.value = value;
        status.append(option);
      });
      status.value = item.attendance_status || "";

      const minutes = input("number", false);
      minutes.min = "0";
      minutes.max = String(maxMinutes);
      minutes.setAttribute("aria-label", `Minutes attended by ${item.full_name}`);
      minutes.value = item.minutes_attended ?? "";

      const row = document.createElement("tr");
      const statusCell = element("td", "");
      statusCell.append(status);
      const minutesCell = element("td", "");
      minutesCell.append(minutes);
      row.append(element("td", "", item.full_name), statusCell, minutesCell);
      body.append(row);

      rows.push({ item, status, minutes });
    });

    table.append(head, body);
    const scroll = element("div", "table-scroll");
    scroll.append(table);

    const allPresent = element("button", "", "Mark everyone present");
    allPresent.type = "button";
    allPresent.addEventListener("click", () => {
      rows.forEach(({ status }) => {
        if (!status.value) status.value = "present";
      });
    });

    const submit = element("button", "", "Save attendance");
    submit.type = "submit";
    const result = note("");
    result.hidden = true;

    form.append(scroll, allPresent, submit, result);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;

      // Only send rows that have a status and have changed.
      const changed = rows.filter(({ item, status, minutes }) => {
        const minutesValue = minutes.value === "" ? null : Number(minutes.value);
        return status.value && (
          status.value !== item.attendance_status ||
          minutesValue !== (item.minutes_attended ?? null)
        );
      });

      result.hidden = false;
      if (!changed.length) {
        result.textContent = "Nothing to save. Choose an attendance status for at least one learner.";
        return;
      }

      submit.disabled = true;
      result.textContent = "Saving attendance…";
      const failures = [];
      for (const { item, status, minutes } of changed) {
        try {
          await window.skillpulseAuth.request(
            `${base}/${session.id}/attendance/${item.learner_id}`,
            {
              method: "PUT",
              headers: jsonHeaders,
              body: JSON.stringify({
                attendance_status: status.value,
                minutes_attended: minutes.value === "" ? null : Number(minutes.value)
              })
            }
          );
        } catch (error) {
          failures.push(`${item.full_name}: ${error.message}`);
        }
      }

      submit.disabled = false;
      const saved = changed.length - failures.length;
      result.textContent = failures.length
        ? `Saved ${saved} of ${changed.length}. Could not save ${failures.join("; ")}`
        : `Attendance saved for ${saved} learner${saved === 1 ? "" : "s"}.`;
      // Reload so the table shows what is now saved.
      if (!failures.length) await reload(result.textContent);
    });

    return form;
  }

  function renderCard(session, reload, openId) {
    const card = element("article", "attendance-card");
    card.dataset.session = session.id;
    card.dataset.status = session.status;

    const tags = element("p", "attendance-tags");
    tags.append(
      element("span", "badge", STATUS_LABEL[session.status] || session.status),
      element("span", "badge", moduleTitle(session.topic_id))
    );
    card.append(
      element("h3", "", session.title),
      tags,
      element("p", "attendance-meta", when(session))
    );

    if (session.status === "scheduled") {
      if (new Date(session.scheduled_end) <= new Date()) {
        const complete = element("button", "", "Mark as completed");
        complete.type = "button";
        complete.addEventListener("click", () =>
          markCompleted(session, complete, card, reload)
        );
        card.append(
          element("p", "attendance-meta", "This class has ended. Mark it as completed to take attendance."),
          complete
        );
      } else {
        card.append(element("p", "attendance-meta", "You can take attendance after the class ends."));
      }
    }

    if (session.status === "completed") {
      const details = element("details", "topic-details");
      const roster = element("div", "");
      details.append(element("summary", "", "Take attendance"), roster);
      let loaded = false;
      details.addEventListener("toggle", () => {
        if (details.open && !loaded) {
          loaded = true;
          loadRoster(session, roster);
        }
      });
      card.append(details);
      if (openId === session.id) details.open = true;
    }

    return card;
  }

  async function load(list, summary, openId = null) {
    list.replaceChildren(note("Loading classes…"));
    try {
      const page = await window.skillpulseAuth.request(
        `${base}?limit=100&offset=0`,
        { headers }
      );
      const sessions = (Array.isArray(page.items) ? page.items : [])
        .sort((a, b) => new Date(b.scheduled_start) - new Date(a.scheduled_start));

      const waiting = sessions.filter(
        (s) => s.status === "scheduled" && new Date(s.scheduled_end) <= new Date()
      ).length;
      summary.textContent = sessions.length
        ? `${sessions.length} class${sessions.length === 1 ? "" : "es"}` +
          (waiting ? ` · ${waiting} ended and waiting to be marked as completed.` : ".")
        : "No classes yet. Add your first class below.";

      const reload = (id) => load(list, summary, id);
      list.replaceChildren();
      sessions.forEach((session) => list.append(renderCard(session, reload, openId)));
    } catch (error) {
      summary.textContent = "";
      list.replaceChildren(note(`Could not load classes: ${error.message}`));
    }
  }

  window.addEventListener("skillpulse:signed-in", (event) => {
    const user = event.detail?.user;
    const isTutor = user?.memberships?.some(
      (membership) =>
        membership.organization_id === pilotContext.organizationId &&
        membership.role === "tutor"
    );
    if (!isTutor || document.getElementById("tutor-attendance")) return;

    const panel = element("section", "card");
    panel.id = "tutor-attendance";
    const summary = element("p", "", "");
    const list = element("div", "attendance-list");

    const add = element("details", "topic-details");
    add.append(
      element("summary", "", "Add a class"),
      addClassForm(() => load(list, summary))
    );

    panel.append(
      element("p", "eyebrow", "CLASSES"),
      element("h2", "", "Classes and attendance"),
      element(
        "p", "",
        "After a class ends, mark it as completed and record who attended. " +
          "Attendance counts towards each learner's exam readiness."
      ),
      summary,
      add,
      list
    );

    const anchor = document.getElementById("tutor-blockers") ||
      document.getElementById("tutor-dashboard");
    if (anchor) anchor.after(panel);
    else document.querySelector(".workspace-header")?.after(panel);

    const nav = document.querySelector(".sidebar nav");
    if (nav) {
      const link = element("a", "", "Attendance");
      link.href = "#tutor-attendance";
      const reviewsLink = nav.querySelector('a[href="#tutor-reviews"]');
      if (reviewsLink) reviewsLink.before(link);
      else nav.append(link);
    }

    load(list, summary);
  });
})();
