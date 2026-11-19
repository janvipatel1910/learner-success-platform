"use strict";

// Learner card: one written assignment per module. The learner submits an
// answer (and an optional HTTPS link); a tutor approves it or asks for changes.
// All assignments must be approved for the certificate.
(() => {
  const anchor = document.getElementById("final-project") ||
    document.getElementById("learning-path");
  if (!anchor) return;

  const section = element("section", "card");
  section.id = "assignments";
  section.style.marginTop = "24px";
  if (anchor.id === "final-project") anchor.before(section);
  else anchor.after(section);

  const base = `/catalog/courses/${pilotContext.courseId}` +
    `/cohorts/${pilotContext.cohortId}/my-assignments`;
  const headers = { "X-Organization-ID": pilotContext.organizationId };

  const STATUS = {
    none: ["Not started", "status-none"],
    submitted: ["Waiting for tutor review", "status-waiting"],
    changes_requested: ["Changes requested", "status-changes"],
    approved: ["Approved", "status-approved"]
  };
  const MIN_ANSWER = 50;
  const MAX_ANSWER = 5000;

  let signedIn = false;
  let busy = false;

  function note(text) {
    const node = element("p", "notice", text);
    node.setAttribute("role", "status");
    return node;
  }

  function safeLink(href, label) {
    try {
      const url = new URL(href);
      if (url.protocol !== "https:" || url.username || url.password) return null;
      const link = element("a", "", label);
      link.href = url.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      return link;
    } catch {
      return null;
    }
  }

  function header(intro) {
    section.replaceChildren(
      element("p", "eyebrow", "ASSIGNMENTS"),
      element("h2", "", "Module assignments"),
      element("p", "", intro)
    );
  }

  function answerForm(assignment) {
    const latest = assignment.latest_submission;
    const form = document.createElement("form");
    form.className = "assignment-form";

    const answerId = `answer-${assignment.assignment_id}`;
    const answerLabel = element("label", "", "Your answer");
    answerLabel.htmlFor = answerId;
    const answer = document.createElement("textarea");
    answer.id = answerId;
    answer.rows = 8;
    answer.required = true;
    answer.minLength = MIN_ANSWER;
    answer.maxLength = MAX_ANSWER;
    answer.placeholder = "Explain your design in your own words.";
    // After "changes requested", start from the previous answer.
    if (latest?.review_status === "changes_requested") {
      answer.value = latest.answer_text;
    }

    const counter = element("p", "form-note", "");
    const updateCounter = () => {
      const length = answer.value.trim().length;
      counter.textContent = length < MIN_ANSWER
        ? `${length} characters · at least ${MIN_ANSWER} needed`
        : `${length} characters`;
    };
    answer.addEventListener("input", updateCounter);
    updateCounter();

    const linkId = `link-${assignment.assignment_id}`;
    const linkLabel = element("label", "", "Link to a diagram or GitHub file (optional)");
    linkLabel.htmlFor = linkId;
    const link = document.createElement("input");
    link.id = linkId;
    link.type = "url";
    link.placeholder = "https://...";
    if (latest?.review_status === "changes_requested" && latest.link_url) {
      link.value = latest.link_url;
    }

    const submit = element(
      "button", "",
      latest ? "Send updated answer" : "Submit for tutor review"
    );
    submit.type = "submit";
    const status = note("");
    status.hidden = true;

    form.append(answerLabel, answer, counter, linkLabel, link, submit, status);

    // Kept between attempts so a retry after a network error is not a duplicate.
    let pending = null;

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (busy) return;
      status.hidden = false;

      if (!pending) {
        const text = answer.value.trim();
        if (text.length < MIN_ANSWER) {
          status.textContent = `Write at least ${MIN_ANSWER} characters.`;
          return;
        }
        const href = link.value.trim();
        if (href && !safeLink(href, "")) {
          status.textContent = "Use an HTTPS link without a username or password, or leave it empty.";
          return;
        }
        pending = {
          submission_id: crypto.randomUUID(),
          answer_text: text,
          link_url: href || null
        };
      }

      busy = true;
      answer.disabled = link.disabled = submit.disabled = true;
      status.textContent = "Sending your answer…";

      try {
        await window.skillpulseAuth.request(
          `${base}/${assignment.assignment_id}/submissions`,
          {
            method: "POST",
            headers: { ...headers, "Content-Type": "application/json" },
            body: JSON.stringify(pending)
          }
        );
      } catch (error) {
        busy = false;
        const code = Number(error.status);
        if ([400, 403, 404, 409, 422].includes(code)) {
          // Rejected for a reason: let the learner change it and try again.
          pending = null;
          answer.disabled = link.disabled = submit.disabled = false;
          status.textContent = `Answer not accepted: ${error.message}`;
        } else {
          submit.disabled = false;
          submit.textContent = "Retry sending";
          status.textContent =
            `Could not confirm your answer was saved: ${error.message}. ` +
            "Press Retry sending; it will not create a duplicate.";
        }
        return;
      }

      busy = false;
      window.dispatchEvent(new Event("skillpulse:assignments-changed"));
      await load("Answer sent. Your tutor will review it and reply here.");
    });

    return form;
  }

  function renderCard(assignment) {
    const latest = assignment.latest_submission;
    const [label, cls] = STATUS[latest?.review_status || "none"] || STATUS.none;

    const card = element("article", "assignment-card");
    card.dataset.status = latest?.review_status || "none";

    const tags = element("p", "assignment-tags");
    tags.append(
      element("span", "badge", assignment.module_title),
      element("span", `badge ${cls}`, label)
    );

    const task = element("details", "topic-details");
    const instructions = element("p", "", assignment.instructions);
    instructions.style.whiteSpace = "pre-wrap";
    task.append(element("summary", "", "Read the task"), instructions);
    if (!latest) task.open = true;

    card.append(element("h3", "", assignment.title), tags, task);

    if (latest) {
      const answerBox = element("div", "assignment-answer");
      const submitted = new Date(latest.submitted_at).toLocaleDateString();
      const answerText = element("p", "", latest.answer_text);
      answerText.style.whiteSpace = "pre-wrap";
      answerBox.append(
        element("h4", "", `Your answer (attempt ${latest.submission_number}, ${submitted})`),
        answerText
      );
      const link = latest.link_url && safeLink(latest.link_url, "Open your link");
      if (link) answerBox.append(link);
      if (latest.tutor_feedback) {
        const feedback = element("p", "", latest.tutor_feedback);
        feedback.style.whiteSpace = "pre-wrap";
        answerBox.append(element("h4", "", "Tutor feedback"), feedback);
      }
      card.append(answerBox);
    }

    if (assignment.can_submit) {
      card.append(answerForm(assignment));
    } else if (assignment.submission_block_reason) {
      card.append(element("p", "form-note", assignment.submission_block_reason));
    }

    return card;
  }

  async function load(message = "") {
    if (!signedIn) return;
    header("Loading your assignments…");
    try {
      const items = await window.skillpulseAuth.request(base, { headers });
      const list = Array.isArray(items) ? items : [];
      const approved = list.filter(
        (item) => item.latest_submission?.review_status === "approved"
      ).length;

      header(
        "One written task per module. Your tutor reads each answer and either " +
          "approves it or asks for changes. All assignments must be approved " +
          "for your certificate."
      );
      if (message) section.append(note(message));
      if (!list.length) {
        section.append(note("No assignments have been published for this course yet."));
        return;
      }
      section.append(element("p", "form-note", `${approved} of ${list.length} approved.`));
      list.forEach((assignment) => section.append(renderCard(assignment)));

      const refresh = element("button", "", "Refresh assignments");
      refresh.type = "button";
      refresh.addEventListener("click", () => load());
      section.append(refresh);
    } catch (error) {
      header("");
      const retry = element("button", "", "Try again");
      retry.type = "button";
      retry.addEventListener("click", () => load());
      section.append(note(`Could not load assignments: ${error.message}`), retry);
    }
  }

  header("Sign in to see your assignments.");

  window.addEventListener("skillpulse:signed-in", (event) => {
    const isLearner = event.detail?.user?.memberships?.some(
      (item) =>
        item.organization_id === pilotContext.organizationId &&
        item.role === "student"
    );
    signedIn = Boolean(isLearner);
    section.hidden = !isLearner;
    if (isLearner) load();
  });
})();
