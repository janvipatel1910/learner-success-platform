"use strict";

// Practice quizzes and timed practice exams for learners.
(() => {
  const learning = document.getElementById("learning");
  if (!learning) return;

  const headers = { "X-Organization-ID": pilotContext.organizationId };
  const base = `/catalog/courses/${pilotContext.courseId}` +
    `/cohorts/${pilotContext.cohortId}/practice-assessments`;

  const section = element("section", "card practice");
  section.id = "practice";
  section.hidden = true;
  learning.after(section);

  const status = element("p", "form-note", "");
  status.setAttribute("role", "status");
  const body = element("div", "");
  section.append(
    element("p", "eyebrow", "TEST YOURSELF"),
    element("h2", "", "Practice quizzes and exams"),
    element(
      "p", "",
      "Untimed quizzes help you learn each topic. The timed exam " +
      "checks you can answer under exam conditions. Every answer " +
      "shows an explanation afterwards."
    ),
    status,
    body
  );

  let timer = null;

  function stopTimer() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  function api(path, options = {}) {
    return window.skillpulseAuth.request(path, {
      ...options,
      headers: { ...headers, ...(options.headers || {}) }
    });
  }

  function formatPercent(value) {
    return value === null || value === undefined
      ? "—"
      : `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
  }

  async function loadList() {
    stopTimer();
    status.textContent = "Loading practice…";
    body.replaceChildren();

    let items;
    try {
      items = await api(base);
    } catch (error) {
      status.textContent = error.message;
      return;
    }

    status.textContent = items.length
      ? ""
      : "No practice quizzes have been published for this course yet.";

    const list = element("div", "practice-list");
    for (const item of items) {
      const row = element("article", "practice-item");
      const kind = item.time_limit_minutes
        ? `Timed · ${item.time_limit_minutes} minutes`
        : "Untimed";
      row.append(
        element("h3", "", item.title),
        element(
          "p", "",
          `${item.question_count} questions · ${kind} · ` +
          `Pass mark ${formatPercent(item.pass_percentage)}`
        ),
        element(
          "p", "practice-meta",
          `Best score: ${formatPercent(item.best_percentage)} · ` +
          `${item.attempts_remaining} of ${item.maximum_attempts} attempts left`
        )
      );

      const start = element(
        "button", "",
        item.in_progress_attempt_id ? "Resume" : "Start"
      );
      start.type = "button";
      start.disabled =
        item.attempts_remaining === 0 && !item.in_progress_attempt_id;
      start.addEventListener("click", () => startAttempt(item));
      row.append(start);
      list.append(row);
    }
    body.append(list);
  }

  async function startAttempt(item) {
    status.textContent = "Preparing your questions…";
    body.replaceChildren();
    try {
      const attempt = await api(
        `${base}/${encodeURIComponent(item.id)}/attempts`,
        { method: "POST" }
      );
      renderAttempt(attempt);
    } catch (error) {
      status.textContent = error.message;
      const back = element("button", "secondary", "Back to practice");
      back.type = "button";
      back.addEventListener("click", loadList);
      body.append(back);
    }
  }

  function renderAttempt(attempt) {
    status.textContent = "";
    const form = element("form", "practice-form");
    const heading = element("div", "practice-heading");
    heading.append(element("h3", "", attempt.title));

    const clock = element("p", "practice-clock", "");
    clock.setAttribute("aria-live", "off");
    heading.append(clock);
    form.append(heading);

    attempt.questions.forEach((question, index) => {
      const fieldset = element("fieldset", "practice-question");
      const multiple = question.question_type === "multiple_choice";
      fieldset.append(
        element(
          "legend", "",
          `${index + 1}. ${question.question_text}`
        ),
        element(
          "p", "practice-meta",
          `${question.topic_title}` +
          (multiple ? ` · Choose ${question.select_count}` : "")
        )
      );

      question.options.forEach((option, optionIndex) => {
        const id = `q-${question.id}-${optionIndex}`;
        const label = element("label", "practice-option");
        const input = document.createElement("input");
        input.type = multiple ? "checkbox" : "radio";
        input.name = question.id;
        input.value = option;
        input.id = id;
        if (multiple) {
          input.addEventListener("change", () => {
            const checked = fieldset.querySelectorAll("input:checked");
            fieldset.querySelectorAll("input").forEach((box) => {
              box.disabled =
                !box.checked && checked.length >= question.select_count;
            });
          });
        }
        label.append(input, document.createTextNode(` ${option}`));
        fieldset.append(label);
      });
      form.append(fieldset);
    });

    const submit = element("button", "", "Submit answers");
    submit.type = "submit";
    form.append(submit);

    async function send() {
      stopTimer();
      submit.disabled = true;
      status.textContent = "Marking your answers…";
      const answers = {};
      for (const question of attempt.questions) {
        const chosen = [
          ...form.querySelectorAll(`input[name="${question.id}"]:checked`)
        ].map((input) => input.value);
        if (chosen.length) answers[question.id] = chosen;
      }
      try {
        const result = await api(
          `${base}/${encodeURIComponent(attempt.assessment_id)}` +
          `/attempts/${encodeURIComponent(attempt.attempt_id)}/submit`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ answers })
          }
        );
        renderResult(result);
        window.dispatchEvent(new Event("skillpulse:modules-changed"));
      } catch (error) {
        status.textContent = error.message;
        submit.disabled = false;
      }
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const unanswered = attempt.questions.filter(
        (q) => !form.querySelector(`input[name="${q.id}"]:checked`)
      ).length;
      if (unanswered && !window.confirm(
        `${unanswered} question(s) are unanswered and will score zero. Submit anyway?`
      )) {
        return;
      }
      send();
    });

    if (attempt.deadline) {
      const deadline = new Date(attempt.deadline).getTime();
      const tick = () => {
        const left = Math.max(0, deadline - Date.now());
        const minutes = Math.floor(left / 60000);
        const seconds = Math.floor((left % 60000) / 1000);
        clock.textContent =
          `Time left: ${minutes}:${String(seconds).padStart(2, "0")}`;
        if (left === 0) send();
      };
      tick();
      timer = setInterval(tick, 1000);
    } else {
      clock.textContent = "No time limit";
    }

    body.replaceChildren(form);
    section.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderResult(result) {
    status.textContent = "";
    const summary = element("div", result.passed ? "notice" : "notice warning");
    summary.append(
      element(
        "strong", "",
        `${result.title}: ${formatPercent(result.percentage)} — ` +
        (result.passed ? "Passed" : "Not passed yet")
      )
    );

    const topics = element("ul", "practice-topics");
    for (const topic of result.topics) {
      topics.append(element(
        "li", "",
        `${topic.topic_title}: ${topic.correct} of ${topic.total} correct`
      ));
    }

    const review = element("ol", "practice-review");
    for (const question of result.questions) {
      const item = element(
        "li", question.is_correct ? "is-correct" : "is-wrong"
      );
      item.append(
        element("p", "practice-review-question", question.question_text),
        element(
          "p", "",
          `Your answer: ${question.selected.length ? question.selected.join(", ") : "No answer"}`
        ),
        element("p", "", `Correct answer: ${question.correct_answer.join(", ")}`),
        element("p", "practice-meta", question.explanation)
      );
      review.append(item);
    }

    const back = element("button", "secondary", "Back to practice");
    back.type = "button";
    back.addEventListener("click", loadList);

    body.replaceChildren(
      summary,
      element("h3", "", "Score by topic"),
      topics,
      element("h3", "", "Review your answers"),
      review,
      back
    );
    section.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  window.addEventListener("skillpulse:signed-in", (event) => {
    const isLearner = event.detail?.user?.memberships?.some(
      (item) =>
        item.organization_id === pilotContext.organizationId &&
        item.role === "student"
    );
    section.hidden = !isLearner;
    if (isLearner) loadList();
    else stopTimer();
  });
})();
