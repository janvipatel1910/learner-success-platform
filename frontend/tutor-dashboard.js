"use strict";

(() => {
  const base = `/catalog/courses/${pilotContext.courseId}` +
    `/cohorts/${pilotContext.cohortId}`;
  const headers = {
    "X-Organization-ID": pilotContext.organizationId
  };

  function note(text) {
    const node = element("p", "notice", text);
    node.setAttribute("role", "status");
    return node;
  }

  function hideStudentPage() {
    [
      "#overview",
      "#connection-status",
      ".summary-grid",
      "#learning",
      "#understanding",
      "#history",
      "#readiness",
      "#next-steps",
      "#support",
      "#final-project"
    ].forEach((selector) => {
      const node = document.querySelector(selector);
      const target = selector === "#next-steps"
        ? node?.closest("section")
        : node;
      if (target) target.style.display = "none";
    });

    const nav = document.querySelector(".sidebar nav");
    if (nav) {
      nav.replaceChildren();
      [
        ["Overview", "#tutor-dashboard"],
        ["Student Understanding", "#tutor-understanding"],
        ["Follow-up Planner", "#tutor-follow-up"],
        ["Project Reviews", "#tutor-reviews"]
      ].forEach(([label, href]) => {
        const link = element("a", "", label);
        link.href = href;
        if (href === "#tutor-follow-up") {
          link.addEventListener("click", () => {
            const details = document.querySelector(
              "#tutor-follow-up details"
            );
            if (details) details.open = true;
          });
        }
        nav.append(link);
      });
    }

    const caption = document.querySelector(".sidebar-caption");
    if (caption) caption.textContent = "TUTOR WORKSPACE";
  }

  function makeMetric(label) {
    const card = element("article", "card");
    card.append(
      element("h2", "", label),
      element("p", "metric", "—")
    );
    return { card, value: card.querySelector(".metric") };
  }

  function localDateTime(minutesFromNow) {
    const value = new Date(Date.now() + minutesFromNow * 60 * 1000);
    value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
    return value.toISOString().slice(0, 16);
  }

  function renderFollowUp(session, items, target) {
    const redCount = items.filter((item) => item.rating === "red").length;
    const yellowCount = items.filter((item) => item.rating === "yellow").length;
    const responses = items.filter((item) => item.rating);

    target.replaceChildren(element("h2", "", "Suggested follow-up"));

    if (!responses.length) {
      target.append(note("No learner feedback has been recorded for this class yet."));
    } else {
      target.append(element(
        "p",
        "",
        `${session.title}: ${redCount} red · ${yellowCount} yellow`
      ));

      if (redCount > 0) {
        target.append(note(
          "Start with a tutor-led recap and guided practice for learners who selected Red."
        ));
      } else if (yellowCount > 0) {
        target.append(note(
          "Use a worked example and leave time for questions from learners who selected Yellow."
        ));
      } else {
        target.append(note(
          "Submitted feedback is Green. Offer an extension exercise or move to the next topic."
        ));
      }
    }

    const details = element("details", "topic-details");
    details.append(element("summary", "", "Schedule follow-up class"));

    const form = document.createElement("form");
    const titleLabel = element("label", "", "Class title");
    const title = document.createElement("input");
    title.type = "text";
    title.required = true;
    title.maxLength = 200;
    title.value = `${session.title} follow-up`;
    titleLabel.append(title);

    const startLabel = element("label", "", "Start date and time");
    const start = document.createElement("input");
    start.type = "datetime-local";
    start.required = true;
    start.value = localDateTime(24 * 60);
    startLabel.append(start);

    const endLabel = element("label", "", "End date and time");
    const end = document.createElement("input");
    end.type = "datetime-local";
    end.required = true;
    end.value = localDateTime(24 * 60 + 45);
    endLabel.append(end);

    const linkLabel = element("label", "", "Class link (optional)");
    const link = document.createElement("input");
    link.type = "url";
    link.placeholder = "https://...";
    linkLabel.append(link);

    const submit = element("button", "", "Create follow-up class");
    submit.type = "submit";
    const status = note("");
    status.hidden = true;

    form.append(titleLabel, startLabel, endLabel, linkLabel, submit, status);
    details.append(form);
    target.append(details);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;

      const startDate = new Date(start.value);
      const endDate = new Date(end.value);
      status.hidden = false;

      if (startDate <= new Date() || endDate <= startDate) {
        status.textContent = "Choose a future start time and an end time after it.";
        return;
      }

      submit.disabled = true;
      status.textContent = "Creating follow-up class…";

      try {
        await window.skillpulseAuth.request(`${base}/sessions`, {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({
            topic_id: session.topic_id,
            title: title.value.trim(),
            scheduled_start: startDate.toISOString(),
            scheduled_end: endDate.toISOString(),
            delivery_link: link.value.trim() || null
          })
        });
        status.textContent =
          `Follow-up class scheduled for ${startDate.toLocaleString()}.`;
        submit.textContent = "Class scheduled";
      } catch (error) {
        status.textContent = `Could not schedule class: ${error.message}`;
        submit.disabled = false;
      }
    });
  }

  async function loadRoster(session, body, metrics, followUp) {
    body.replaceChildren();
    body.append(note("Loading learner feedback…"));

    try {
      const result = await window.skillpulseAuth.request(
        `${base}/sessions/${session.id}/understanding-checks` +
          "?limit=100&offset=0",
        { headers }
      );

      const items = result.items || [];
      renderFollowUp(session, items, followUp);
      const counts = { green: 0, yellow: 0, red: 0 };
      items.forEach((item) => {
        if (item.rating && counts[item.rating] !== undefined) {
          counts[item.rating] += 1;
        }
      });

      metrics.green.textContent = String(counts.green);
      metrics.yellow.textContent = String(counts.yellow);
      metrics.red.textContent = String(counts.red);

      body.replaceChildren();
      if (!items.length) {
        body.append(note("No understanding feedback has been recorded for this class yet."));
        return;
      }

      const table = document.createElement("table");
      const head = document.createElement("thead");
      const headerRow = document.createElement("tr");
      ["Learner", "Understanding", "Comment"].forEach((label) => {
        headerRow.append(element("th", "", label));
      });
      head.append(headerRow);

      const rows = document.createElement("tbody");
      items.forEach((item) => {
        const row = document.createElement("tr");
        const rating = item.rating
          ? item.rating[0].toUpperCase() + item.rating.slice(1)
          : "No response yet";
        row.append(
          element("td", "", item.full_name),
          element("td", item.rating || "", rating),
          element("td", "", item.comment || "—")
        );
        rows.append(row);
      });

      table.append(head, rows);
      const scroll = element("div", "table-scroll");
      scroll.append(table);
      body.append(scroll);
    } catch (error) {
      body.replaceChildren(note(`Could not load understanding checks: ${error.message}`));
    }
  }

  window.addEventListener("skillpulse:signed-in", async (event) => {
    const user = event.detail?.user;
    const isTutor = user?.memberships?.some(
      (membership) =>
        membership.organization_id === pilotContext.organizationId &&
        membership.role === "tutor"
    );
    if (!isTutor) return;

    hideStudentPage();

    const dashboard = element("section", "card");
    dashboard.id = "tutor-dashboard";
    dashboard.style.marginTop = "24px";
    dashboard.append(
      element("p", "eyebrow", "TUTOR WORKSPACE"),
      element("h1", "", "Welcome, " + user.full_name),
      element("p", "", "Review learner feedback and plan your next class.")
    );

    const metricsGrid = element("div", "summary-grid");
    const green = makeMetric("Green · Understood");
    const yellow = makeMetric("Yellow · Some doubts");
    const red = makeMetric("Red · Need help");
    metricsGrid.append(green.card, yellow.card, red.card);

    const followUp = element("section", "card");
    followUp.id = "tutor-follow-up";
    followUp.append(
      element("h2", "", "Suggested follow-up"),
      note("Select a completed class to see a teaching suggestion.")
    );

    const panel = element("section", "card");
    panel.id = "tutor-understanding";
    panel.append(
      element("h2", "", "Student understanding by class"),
      element("p", "", "Use this feedback to choose topics for follow-up teaching.")
    );

    const selectLabel = element("label", "", "Completed class session");
    const select = document.createElement("select");
    selectLabel.append(select);
    const roster = element("div", "");
    panel.append(selectLabel, roster);
    dashboard.append(metricsGrid, followUp, panel);

    const header = document.querySelector(".workspace-header");
    if (header) header.after(dashboard);
    else document.querySelector("main").prepend(dashboard);

    const reviews = document.getElementById("tutor-reviews");
    if (reviews) dashboard.after(reviews);

    try {
      const result = await window.skillpulseAuth.request(
        `${base}/sessions?limit=100&offset=0`,
        { headers }
      );
      const sessions = (result.items || [])
        .filter((session) => session.status === "completed")
        .sort((a, b) =>
          new Date(b.scheduled_start) - new Date(a.scheduled_start)
        );

      if (!sessions.length) {
        roster.replaceChildren(note("No completed class sessions are available yet."));
        return;
      }

      sessions.forEach((session) => {
        const option = document.createElement("option");
        option.value = session.id;
        option.textContent =
          `${session.title} · ${new Date(session.scheduled_start).toLocaleDateString()}`;
        select.append(option);
      });

      const metrics = {
        green: green.value,
        yellow: yellow.value,
        red: red.value
      };

      const showSelected = () => {
        const session = sessions.find((item) => item.id === select.value);
        if (session) loadRoster(session, roster, metrics, followUp);
      };

      select.addEventListener("change", showSelected);
      showSelected();
    } catch (error) {
      roster.replaceChildren(note(`Could not load class sessions: ${error.message}`));
    }
  });
})();
