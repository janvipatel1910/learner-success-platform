"use strict";

(() => {
  const learningPath = document.getElementById("learning-path");
  if (!learningPath) return;

  const section = element("section", "card");
  section.id = "tutor-reviews";
  section.style.marginTop = "24px";
  learningPath.after(section);

  const base =
    `/catalog/courses/${pilotContext.courseId}` +
    `/cohorts/${pilotContext.cohortId}/final-project/submissions`;
  const headers = {
    "X-Organization-ID": pilotContext.organizationId
  };

  const labels = {
    submitted: "Awaiting review",
    under_review: "Under review",
    changes_requested: "Changes requested",
    approved: "Approved",
    rejected: "Rejected"
  };

  function message(text) {
    const node = element("p", "notice", text);
    node.setAttribute("role", "status");
    return node;
  }

  function addScore(container, score, maximum) {
    if (score === null || score === undefined || Number(maximum) <= 0) return;

    const percent = Math.max(
      0,
      Math.min(100, (Number(score) / Number(maximum)) * 100)
    );
    const block = element("div", "review-score");
    const label = element(
      "p",
      "",
      `Score: ${score} / ${maximum} (${percent.toFixed(0)}%)`
    );
    const track = element("div", "review-score-track");
    const fill = element("div", "review-score-fill");
    fill.style.width = `${percent}%`;
    track.setAttribute("role", "progressbar");
    track.setAttribute("aria-label", "Project score");
    track.setAttribute("aria-valuemin", "0");
    track.setAttribute("aria-valuemax", "100");
    track.setAttribute("aria-valuenow", String(Math.round(percent)));
    track.append(fill);
    block.append(label, track);
    container.append(block);
  }

  function makeCard(submission) {
    const card = element("article", "review-card");
    const currentStatus = submission.review_status;
    const statusClass = `review-status-${currentStatus.replaceAll("_", "-")}`;
    const isAwaitingReview = ["submitted", "under_review"].includes(currentStatus);

    const details = document.createElement("details");
    details.open = isAwaitingReview;

    const summary = document.createElement("summary");
    summary.className = "review-card-summary";
    summary.append(
      element(
        "strong",
        "",
        `${submission.learner_name} · Submission ${submission.submission_number}`
      ),
      element(
        "span",
        `review-status ${statusClass}`,
        labels[currentStatus] || currentStatus
      )
    );
    details.append(summary);

    const content = element("div", "review-card-content");
    content.append(
      element("h3", "", submission.project_title),
      element("p", "review-note", submission.note)
    );

    const projectLink = element("a", "review-project-link", "Open submitted project ↗");
    projectLink.href = submission.submission_url;
    projectLink.target = "_blank";
    projectLink.rel = "noopener noreferrer";
    content.append(projectLink);

    if (!isAwaitingReview) {
      addScore(content, submission.score, submission.maximum_score);

      if (submission.tutor_feedback) {
        content.append(
          element("h4", "", "Tutor feedback"),
          element("p", "review-feedback", submission.tutor_feedback)
        );
      }

      content.append(message("This submission has a final review."));
      details.append(content);
      card.append(details);
      return card;
    }

    const form = document.createElement("form");
    form.className = "review-form";

    const decisionLabel = element("label", "", "Review decision");
    const decision = document.createElement("select");
    decision.required = true;
    decision.append(new Option("Choose a decision", ""));
    if (currentStatus === "submitted") {
      decision.append(new Option("Move to under review", "under_review"));
    }
    decision.append(
      new Option("Request changes", "changes_requested"),
      new Option("Approve", "approved"),
      new Option("Reject", "rejected")
    );
    decisionLabel.append(decision);

    const scoreLabel = element("label", "", "Score");
    const score = document.createElement("input");
    score.type = "number";
    score.min = "0";
    score.max = String(submission.maximum_score);
    score.step = "0.01";
    score.placeholder = `Up to ${submission.maximum_score}`;
    scoreLabel.append(score);

    const feedbackLabel = element("label", "", "Feedback for the learner");
    const feedback = document.createElement("textarea");
    feedback.required = true;
    feedback.minLength = 10;
    feedback.maxLength = 5000;
    feedback.rows = 4;
    feedback.placeholder = "Give clear, helpful feedback (at least 10 characters).";
    feedbackLabel.append(feedback);

    const status = message("");
    status.hidden = true;
    const save = element("button", "", "Save review");
    save.type = "submit";

    form.append(decisionLabel, scoreLabel, feedbackLabel, save, status);
    content.append(form);
    details.append(content);
    card.append(details);

    decision.addEventListener("change", () => {
      const approving = decision.value === "approved";
      const movingToReview = decision.value === "under_review";
      score.required = approving;
      score.disabled = movingToReview;
      if (movingToReview) score.value = "";
      scoreLabel.classList.toggle("is-required", approving);
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;

      status.hidden = false;
      status.textContent = "Saving review…";
      save.disabled = true;

      try {
        await window.skillpulseAuth.request(
          `${base}/${submission.submission_id}/review`,
          {
            method: "PUT",
            headers: { ...headers, "Content-Type": "application/json" },
            body: JSON.stringify({
              expected_review_status: currentStatus,
              review_status: decision.value,
              score: score.value === "" ? null : Number(score.value),
              tutor_feedback: feedback.value.trim()
            })
          }
        );
        await load();
      } catch (error) {
        status.textContent = `Review not saved: ${error.message}`;
        save.disabled = false;
      }
    });

    return card;
  }

  async function load() {
    section.replaceChildren(
      element("p", "eyebrow", "TUTOR WORKSPACE"),
      element("h2", "", "Final project reviews"),
      message("Loading submissions…")
    );

    try {
      const result = await window.skillpulseAuth.request(
        `${base}?limit=100&offset=0`,
        { headers }
      );

      section.replaceChildren(
        element("p", "eyebrow", "TUTOR WORKSPACE"),
        element("h2", "", "Final project reviews"),
        element(
          "p",
          "review-intro",
          "Search submissions, filter by review status, and open a card to review its details."
        )
      );

      const toolbar = element("div", "review-toolbar");
      const searchLabel = element("label", "", "Search submissions");
      const search = document.createElement("input");
      search.type = "search";
      search.placeholder = "Search learner or project";
      searchLabel.append(search);

      const filterLabel = element("label", "", "Filter by status");
      const filter = document.createElement("select");
      [
        ["all", "All submissions"],
        ["submitted", "Awaiting review"],
        ["under_review", "Under review"],
        ["changes_requested", "Changes requested"],
        ["approved", "Approved"],
        ["rejected", "Rejected"]
      ].forEach(([value, label]) => filter.append(new Option(label, value)));
      filterLabel.append(filter);
      toolbar.append(searchLabel, filterLabel);

      const refresh = element("button", "review-refresh", "Refresh submissions");
      refresh.type = "button";

      const list = element("div", "review-list");
      const empty = message("No submissions match these filters.");
      empty.hidden = true;

      section.append(toolbar, refresh, list, empty);

      const items = result.items || [];
      if (!items.length) {
        list.append(message("No project submissions have been received yet."));
        return;
      }

      const cards = items.map((submission) => {
        const card = makeCard(submission);
        card.dataset.status = submission.review_status;
        card.dataset.search =
          `${submission.learner_name} ${submission.project_title}`.toLowerCase();
        list.append(card);
        return card;
      });

      function applyFilters() {
        const query = search.value.trim().toLowerCase();
        const selectedStatus = filter.value;
        let visible = 0;

        cards.forEach((card) => {
          const matchesText = card.dataset.search.includes(query);
          const matchesStatus =
            selectedStatus === "all" || card.dataset.status === selectedStatus;
          card.hidden = !(matchesText && matchesStatus);
          if (!card.hidden) visible += 1;
        });

        empty.hidden = visible !== 0;
      }

      search.addEventListener("input", applyFilters);
      filter.addEventListener("change", applyFilters);
      refresh.addEventListener("click", load);
    } catch (error) {
      section.replaceChildren(
        element("p", "eyebrow", "TUTOR WORKSPACE"),
        element("h2", "", "Final project reviews"),
        message(
          Number(error.status) === 403
            ? "Tutor access was denied. Check that this account is assigned to the cohort."
            : `Could not load submissions: ${error.message}`
        )
      );
    }
  }

  window.addEventListener("skillpulse:signed-in", (event) => {
    const isTutor = event.detail?.user?.memberships?.some(
      (item) =>
        item.organization_id === pilotContext.organizationId &&
        item.role === "tutor"
    );

    if (!isTutor) {
      section.hidden = true;
      return;
    }

    section.hidden = false;
    load();
  });
})();
