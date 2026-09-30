
"use strict";

const pilotContext = {
  organizationId: "10000000-0000-0000-0000-000000000001",
  courseId: "40000000-0000-0000-0000-000000000001",
  cohortId: "42000000-0000-0000-0000-000000000001"
};

const coursePreview = {
  title: "AWS Solutions Architect Associate Readiness",
  topics: [
    {
      title: "Networking and VPC",
      hours: 6,
      domain: "Design Secure Architectures",
      objectives: [
        "Explain VPCs, subnets and route tables.",
        "Compare public and private network access.",
        "Describe security groups and network ACLs."
      ],
      activity:
        "Draw a VPC with public and private subnets. Explain how traffic reaches each subnet."
    },
    {
      title: "Storage and S3",
      hours: 5,
      domain: "Design Resilient Architectures",
      objectives: [
        "Explain S3 buckets, objects and access permissions.",
        "Describe how versioning helps recover object changes.",
        "Compare storage options for different access needs."
      ],
      activity:
        "Design a private document-storage solution and explain how you would protect and recover files."
    }
  ]
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value;
}

function formatScore(value) {
  if (value === null || value === undefined) return "—";
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : "—";
}

function readinessLabel(level) {
  return {
    ready: "Ready",
    nearly_ready: "Nearly ready",
    developing: "Developing",
    not_ready: "Not ready"
  }[level] || "Unknown";
}

function renderLearningPath() {
  const container = document.getElementById("learning-path");
  container.className = "learning-path";
  container.replaceChildren();

  const overview = element("div", "course-overview");
  overview.append(
    element("span", "badge", "Demo course preview"),
    element("h3", "", coursePreview.title),
    element("p", "", "AWS-SAA-DEMO · 2 topics · 11 estimated learning hours"),
    element("p", "form-note",
      "Static preview of the synthetic course. Study outlines are draft content, not completion records.")
  );
  container.append(overview);

  coursePreview.topics.forEach((topic, index) => {
    const card = element("article", "topic-card");
    const header = element("div", "topic-header");
    const heading = element("div", "");
    heading.append(
      element("h3", "", topic.title),
      element("p", "topic-meta",
        `${topic.hours} estimated hours · ${topic.domain}`)
    );
    header.append(
      element("span", "topic-number", String(index + 1).padStart(2, "0")),
      heading
    );

    const details = element("details", "topic-details");
    const objectives = element("ul", "");
    topic.objectives.forEach((text) => {
      objectives.append(element("li", "", text));
    });
    details.append(
      element("summary", "", "View study outline"),
      element("h4", "", "Learning objectives"),
      objectives,
      element("h4", "", "Practice activity"),
      element("p", "", topic.activity),
      element("p", "form-note",
        "Preview activity only. No submission or completion is recorded here.")
    );
    card.append(header, details);
    container.append(card);
  });
}

function renderReadiness(data) {
  const components = data.explanation_json.components;
  const gates = data.explanation_json.gates;
  const thresholds = data.thresholds;

  setText("overall-score", formatScore(data.overall_score));
  setText("readiness-level", readinessLabel(data.readiness_level));

  for (const name of ["quiz", "mock", "lab", "attendance", "blockers"]) {
    setText(`${name}-score`, `${formatScore(components[name])}%`);
  }
  setText("attendance-summary", `${formatScore(components.attendance)}%`);
  setText("labs-summary", `${formatScore(components.lab)}%`);
  setText("readiness-summary",
    "Calculated from current demo records. Blocker resolution is a score, not a blocker count.");

  const requirements = [
    [gates.overall_threshold_met, "Overall score",
      thresholds.readiness_threshold,
      "Review the lower-scoring learning areas."],
    [gates.minimum_mock_score_met, "Mock exam score",
      thresholds.minimum_mock_score,
      "Review mock exam mistakes and practise weak topics."],
    [gates.minimum_lab_completion_met, "Lab completion",
      thresholds.minimum_lab_completion,
      "Complete outstanding labs and check tutor feedback."]
  ];

  const list = document.getElementById("readiness-requirements");
  list.replaceChildren();
  requirements.forEach(([met, label, minimum]) => {
    list.append(element("li", "",
      `${met ? "✓ Met" : "! Not met"} — ${label}: at least ${minimum}%`));
  });

  const next = document.getElementById("next-steps");
  next.replaceChildren();
  const unmet = requirements.filter(([met]) => !met);

  if (!unmet.length) {
    next.append(element("p", "",
      "All current readiness requirements are met. Continue revising and discuss your exam plan with your tutor."));
  } else {
    const actions = element("ul", "");
    unmet.forEach((requirement) => {
      actions.append(element("li", "", requirement[3]));
    });
    next.append(actions);
  }
}

function showHistoryMessage(message) {
  const row = element("tr", "");
  const cell = element("td", "", message);
  cell.colSpan = 3;
  row.append(cell);
  document.getElementById("history-body").replaceChildren(row);
}

function renderReadinessHistory(snapshots) {
  if (!Array.isArray(snapshots)) {
    throw new Error("Unexpected history response.");
  }
  if (!snapshots.length) {
    showHistoryMessage("No snapshots saved yet.");
    return;
  }

  const body = document.getElementById("history-body");
  body.replaceChildren();
  snapshots.forEach((snapshot) => {
    const date = new Date(snapshot.calculated_at);
    const row = element("tr", "");
    row.append(
      element("td", "", Number.isNaN(date.getTime())
        ? "Date unavailable" : date.toLocaleString()),
      element("td", "", `${formatScore(snapshot.overall_score)} / 100`),
      element("td", "", readinessLabel(snapshot.readiness_level))
    );
    body.append(row);
  });
}

renderLearningPath();

window.addEventListener("skillpulse:signed-in", async () => {
  const base = `/catalog/courses/${pilotContext.courseId}` +
    `/cohorts/${pilotContext.cohortId}/readiness/me`;
  const options = {
    headers: { "X-Organization-ID": pilotContext.organizationId }
  };

  setText("connection-status", "Signed in. Loading readiness and history…");

  const results = await Promise.allSettled([
    window.skillpulseAuth.request(base, options),
    window.skillpulseAuth.request(
      `${base}/snapshots?limit=20&offset=0`, options)
  ]);

  const errors = [];
  try {
    if (results[0].status === "rejected") throw results[0].reason;
    renderReadiness(results[0].value);
  } catch (error) {
    setText("readiness-summary", "Readiness could not be loaded.");
    errors.push(`Readiness: ${error.message}`);
  }

  try {
    if (results[1].status === "rejected") throw results[1].reason;
    renderReadinessHistory(results[1].value);
  } catch (error) {
    showHistoryMessage("History could not be loaded.");
    errors.push(`History: ${error.message}`);
  }

  setText("connection-status", errors.length
    ? `Signed in. ${errors.join(" ")}`
    : "Connected to demo learner records. Readiness and history loaded. " +
      "See My Understanding for feedback status. Support is not connected yet.");
});

;
(() => {
  const form = document.getElementById("understanding-form");
  const fieldset = form.querySelector("fieldset");
  const sessionSelect = document.getElementById("session-select");
  const ratingSelect = document.getElementById("understanding-rating");
  const commentInput = document.getElementById("understanding-comment");
  const saveButton = form.querySelector('button[type="submit"]');
  const note = form.querySelector(".form-note");

  const labels = {
    green: "Green · Understood",
    yellow: "Yellow · Some doubts",
    red: "Red · Need help"
  };

  const base =
    `/catalog/courses/${pilotContext.courseId}` +
    `/cohorts/${pilotContext.cohortId}/sessions`;

  const headers = {
    "X-Organization-ID": pilotContext.organizationId
  };

  let loadVersion = 0;

  note.setAttribute("role", "status");
  ratingSelect.required = true;
  sessionSelect.required = true;
  commentInput.maxLength = 2000;

  const summary = document.getElementById("understanding-summary");
  summary.parentElement.querySelector("p:last-child").textContent =
    "Saved feedback for the selected class.";

  function lockFields(locked) {
    ratingSelect.disabled = locked;
    commentInput.disabled = locked;
    saveButton.disabled = locked;
  }

  function checkPath(sessionId) {
    return `${base}/${encodeURIComponent(sessionId)}/my-understanding-check`;
  }

  function showSaved(check) {
    ratingSelect.value = check.rating;
    commentInput.value = check.comment || "";
    summary.textContent = labels[check.rating] || "Unknown";
  }

  async function loadSelectedCheck() {
    const version = ++loadVersion;
    const sessionId = sessionSelect.value;

    ratingSelect.value = "";
    commentInput.value = "";
    summary.textContent = "—";
    lockFields(true);

    if (!sessionId) {
      note.textContent = "Choose a completed class.";
      return;
    }

    note.textContent = "Loading your saved feedback…";

    try {
      const check = await window.skillpulseAuth.request(
        checkPath(sessionId),
        { headers }
      );

      if (version !== loadVersion) return;

      showSaved(check);
      note.textContent =
        "Saved feedback loaded. Saving again updates this class's record.";
      lockFields(false);
    } catch (error) {
      if (version !== loadVersion) return;

      if (error.status === 404) {
        note.textContent =
          "No feedback record was found. Choose your understanding status.";
        lockFields(false);
      } else {
        note.textContent = `Could not load feedback. ${error.message}`;
      }
    }
  }

  sessionSelect.addEventListener("change", loadSelectedCheck);

  window.addEventListener("skillpulse:signed-in", async () => {
    fieldset.disabled = true;
    note.textContent = "Loading classes…";

    try {
      const sessions = [];
      let offset = 0;

      while (true) {
        const page = await window.skillpulseAuth.request(
          `${base}?limit=100&offset=${offset}`,
          { headers }
        );

        if (!Array.isArray(page.items)) {
          throw new Error("Unexpected class-list response.");
        }

        sessions.push(...page.items);
        offset += page.items.length;

        if (offset >= page.total || page.items.length === 0) break;
      }

      const completed = sessions
        .filter((session) => session.status === "completed")
        .sort(
          (a, b) => new Date(b.scheduled_start) - new Date(a.scheduled_start)
        );

      sessionSelect.replaceChildren();

      if (completed.length === 0) {
        sessionSelect.append(new Option("No completed classes yet", ""));
        note.textContent =
          "Understanding feedback becomes available after a class is completed.";
        return;
      }

      for (const session of completed) {
        const date = new Date(session.scheduled_start).toLocaleDateString();
        sessionSelect.append(
          new Option(`${session.title} · ${date}`, session.id)
        );
      }

      fieldset.disabled = false;
      await loadSelectedCheck();
    } catch (error) {
      note.textContent = `Could not load classes. ${error.message}`;
    }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!form.reportValidity() || saveButton.disabled) return;

    const sessionId = sessionSelect.value;
    const payload = {
      rating: ratingSelect.value,
      comment: commentInput.value.trim() || null
    };

    sessionSelect.disabled = true;
    lockFields(true);
    note.textContent = "Saving your understanding…";

    try {
      const saved = await window.skillpulseAuth.request(
        checkPath(sessionId),
        {
          method: "PUT",
          headers: {
            ...headers,
            "Content-Type": "application/json"
          },
          body: JSON.stringify(payload)
        }
      );

      showSaved(saved);
      note.textContent =
        "Understanding saved. Your tutor can view this feedback.";
    } catch (error) {
      note.textContent =
        `Save could not be confirmed. ${error.message} ` +
        "Your selection and comment are still in the form.";
    } finally {
      sessionSelect.disabled = false;
      lockFields(false);
    }
  });
})();
