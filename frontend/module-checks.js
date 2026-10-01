"use strict";

(() => {
  const headers = {
    "X-Organization-ID": pilotContext.organizationId
  };
  const base = `/catalog/courses/${pilotContext.courseId}` +
    `/cohorts/${pilotContext.cohortId}`;

  const feedback = element("p", "notice", "");
  feedback.setAttribute("role", "status");
  feedback.hidden = true;
  document.getElementById("learning-path").before(feedback);

  function announce(text) {
    feedback.textContent = text;
    feedback.hidden = false;
    feedback.tabIndex = -1;
    requestAnimationFrame(() => {
      feedback.focus({ preventScroll: true });
      feedback.scrollIntoView({
        behavior: "auto",
        block: "center"
      });
    });
  }

  async function refreshReadiness() {
    try {
      const data = await window.skillpulseAuth.request(
        `${base}/readiness/me`, { headers }
      );
      renderReadiness(data);
    } catch {
      announce(
        feedback.textContent +
        " Readiness could not be refreshed; refresh the dashboard later."
      );
    }
  }

  function mount(card, module) {
    if (module.status !== "in_progress") return;

    const section = element("section", "topic-details");
    const open = element("button", "", "Take module check");
    open.type = "button";

    const content = element("div", "");
    const notice = element("p", "form-note", "");
    notice.setAttribute("role", "status");
    section.append(open, notice, content);
    card.append(section);

    const checkPath =
      `${base}/my-modules/${encodeURIComponent(module.topic_id)}/check`;

    async function loadCheck() {
      open.disabled = true;
      content.replaceChildren();
      notice.textContent = "Loading module check…";

      try {
        const check = await window.skillpulseAuth.request(
          checkPath, { headers }
        );

        if (check.module_status === "completed") {
          notice.textContent = "This module is already completed.";
          window.dispatchEvent(new Event("skillpulse:modules-changed"));
          return;
        }

        notice.textContent =
          `${check.title} · Pass mark: ${check.pass_percentage}% · ` +
          `${check.attempts_remaining} attempts remaining.`;

        if (check.attempts_remaining === 0) {
          notice.textContent += " Contact your tutor for help.";
          return;
        }

        const form = element("form", "");
        const fields = element("fieldset", "");
        fields.append(element("legend", "", "Answer every question"));

        check.questions.forEach((question, index) => {
          const group = element("fieldset", "");
          group.append(element(
            "legend", "", `${index + 1}. ${question.question_text}`
          ));

          question.options.forEach((option) => {
            const label = element("label", "");
            const radio = document.createElement("input");
            radio.type = "radio";
            radio.name = question.id;
            radio.value = option;
            radio.required = true;

            label.append(radio, document.createTextNode(` ${option}`));
            group.append(label, document.createElement("br"));
          });
          fields.append(group);
        });

        const submit = element("button", "", "Submit answers");
        submit.type = "submit";
        form.append(fields, submit);
        content.append(form);

        let sending = false;
        let pendingPayload = null;

        form.addEventListener("submit", async (event) => {
          event.preventDefault();
          if (sending) return;

          if (!pendingPayload) {
            if (!form.reportValidity()) return;

            const data = new FormData(form);
            const answers = {};
            check.questions.forEach((question) => {
              answers[question.id] = [data.get(question.id)];
            });

            pendingPayload = {
              attempt_id: crypto.randomUUID(),
              version: check.version,
              answers
            };
          }

          sending = true;
          fields.disabled = true;
          submit.disabled = true;
          notice.textContent = "Submitting answers…";

          try {
            const result = await window.skillpulseAuth.request(
              `${checkPath}/attempts`,
              {
                method: "POST",
                headers: {
                  ...headers,
                  "Content-Type": "application/json"
                },
                body: JSON.stringify(pendingPayload)
              }
            );

            content.replaceChildren();
            const resultText = result.passed
              ? `${module.title}: ${result.percentage}% — Passed. ` +
                "Module completed. Your module list is being refreshed."
              : `${module.title}: ${result.percentage}% — Not passed. ` +
                "Review the study outline before trying again.";

            notice.textContent = resultText;
            announce(resultText);

            if (result.passed) {
              window.dispatchEvent(new Event("skillpulse:modules-changed"));
            } else {
              open.textContent = "Try module check again";
              open.disabled = false;
            }

            await refreshReadiness();
          } catch (error) {
            const status = Number(error.status);

            if ([400, 403, 404, 409, 422].includes(status)) {
              content.replaceChildren();
              notice.textContent = `Check not accepted: ${error.message}`;
              open.textContent = "Reload module check";
              open.disabled = false;
            } else {
              // Keep the same attempt ID and answers after an uncertain
              // response, so retrying does not consume another attempt.
              notice.textContent =
                `Could not confirm the result: ${error.message}. ` +
                "Retry this submission without refreshing the page. " +
                "If your session expired, sign in again.";
              submit.textContent = "Retry same submission";
              submit.disabled = false;
            }
          } finally {
            sending = false;
          }
        });
      } catch (error) {
        notice.textContent = `Check could not be loaded: ${error.message}`;
        open.textContent = "Retry loading check";
        open.disabled = false;
      }
    }

    open.addEventListener("click", loadCheck);
  }

  window.skillpulseModuleChecks = { mount };
})();
