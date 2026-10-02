"use strict";

(() => {
  const learningPath = document.getElementById("learning-path");
  if (!learningPath) return;

  const section = element("section", "card");
  section.id = "final-project";
  section.style.marginTop = "24px";
  learningPath.after(section);

  const base = `/catalog/courses/${pilotContext.courseId}` +
    `/cohorts/${pilotContext.cohortId}/my-final-project`;
  const headers = {
    "X-Organization-ID": pilotContext.organizationId
  };

  const labels = {
    submitted: "Submitted — awaiting tutor review",
    under_review: "Under review",
    changes_requested: "Changes requested",
    approved: "Approved",
    rejected: "Rejected"
  };

  let busy = false;
  let signedIn = false;

  function showStatus(text) {
    const node = element("p", "notice", text);
    node.setAttribute("role", "status");
    return node;
  }

  function render(project, message = "") {
    section.replaceChildren(
      element("p", "eyebrow", "FINAL PROJECT"),
      element("h2", "", project.title)
    );

    if (message) section.append(showStatus(message));

    const brief = element("details", "topic-details");
    const instructions = element("p", "", project.instructions);
    instructions.style.whiteSpace = "pre-wrap";
    brief.append(
      element("summary", "", "Read project brief and submission requirements"),
      instructions
    );
    section.append(
      brief,
      element(
        "p", "form-note",
        `${project.modules_completed} of ${project.modules_total} modules completed.`
      )
    );

    const latest = project.latest_submission;

    if (latest) {
      const history = element("div", "course-overview");
      history.append(
        element("h3", "", `Submission ${latest.submission_number}`),
        element("p", "", labels[latest.review_status] || latest.review_status),
        element("p", "", latest.note)
      );

      try {
        const url = new URL(latest.submission_url);
        if (url.protocol === "https:" && !url.username && !url.password) {
          const link = element("a", "", "Open submitted project");
          link.href = url.href;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          history.append(link);
        }
      } catch {
        history.append(element("p", "", "Submission link is unavailable."));
      }

      if (latest.score !== null) {
        history.append(element(
          "p", "", `Score: ${latest.score} / ${project.maximum_score}`
        ));
      }

      if (latest.tutor_feedback) {
        history.append(
          element("h4", "", "Tutor feedback"),
          element("p", "", latest.tutor_feedback)
        );
      }
      section.append(history);
    }

    const refresh = element("button", "", "Refresh project status");
    refresh.type = "button";
    refresh.addEventListener("click", () => load());
    section.append(refresh);

    if (!project.can_submit) {
      section.append(showStatus(
        project.submission_block_reason || "Submission is unavailable."
      ));
      return;
    }

    const form = element("form", "");
    const fields = element("fieldset", "");
    fields.append(element("legend", "", "Submit your project"));

    const urlLabel = element("label", "", "HTTPS project link");
    const url = document.createElement("input");
    url.id = "final-project-url";
    url.type = "url";
    url.required = true;
    url.placeholder = "https://github.com/your-name/your-project";
    url.style.width = "100%";
    url.style.padding = "12px";
    urlLabel.htmlFor = url.id;

    const noteLabel = element("label", "", "What have you included?");
    const note = document.createElement("textarea");
    note.id = "final-project-note";
    note.required = true;
    note.minLength = 10;
    note.maxLength = 5000;
    note.rows = 4;
    noteLabel.htmlFor = note.id;

    fields.append(urlLabel, url, noteLabel, note);
    const submit = element("button", "", "Submit for tutor review");
    submit.type = "submit";
    const status = showStatus("");
    status.hidden = true;
    form.append(fields, submit, status);
    section.append(form);

    let pendingPayload = null;

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (busy) return;

      status.hidden = false;

      if (!pendingPayload) {
        if (!form.reportValidity()) return;

        let parsed;
        try {
          parsed = new URL(url.value.trim());
        } catch {
          status.textContent = "Enter a valid HTTPS link.";
          return;
        }

        if (
          parsed.protocol !== "https:" ||
          parsed.username ||
          parsed.password
        ) {
          status.textContent = "Use an HTTPS link without embedded credentials.";
          return;
        }

        if (note.value.trim().length < 10) {
          status.textContent = "Add a submission note of at least 10 characters.";
          return;
        }

        pendingPayload = {
          submission_id: crypto.randomUUID(),
          submission_url: parsed.href,
          note: note.value.trim()
        };
      }

      busy = true;
      fields.disabled = true;
      submit.disabled = true;
      refresh.disabled = true;
      status.textContent = "Submitting project…";

      try {
        await window.skillpulseAuth.request(
          `${base}/submissions`,
          {
            method: "POST",
            headers: { ...headers, "Content-Type": "application/json" },
            body: JSON.stringify(pendingPayload)
          }
        );
      } catch (error) {
        busy = false;
        const code = Number(error.status);

        if ([400, 403, 404, 409, 422].includes(code)) {
          status.textContent = `Submission not accepted: ${error.message}`;
          pendingPayload = null;
          fields.disabled = false;
          submit.disabled = false;
          refresh.disabled = false;
        } else {
          status.textContent =
            `Could not confirm submission: ${error.message}. ` +
            "Retry the same submission without refreshing this page. " +
            "If your session expired, sign in again.";
          submit.textContent = "Retry same submission";
          submit.disabled = false;
        }
        return;
      }

      busy = false;
      await load("Project submitted. Your tutor must review it before approval.");
    });
  }

  async function load(message = "") {
    if (!signedIn || busy) return;
    busy = true;
    section.replaceChildren(
      element("h2", "", "Final project"),
      showStatus(message || "Loading final project…")
    );

    try {
      const project = await window.skillpulseAuth.request(base, { headers });
      render(project, message);
    } catch (error) {
      const retry = element("button", "", "Retry loading project");
      retry.type = "button";
      retry.addEventListener("click", () => load(message));
      section.append(
        showStatus(`Project could not be loaded: ${error.message}`),
        retry
      );
    } finally {
      busy = false;
    }
  }

  section.append(
    element("h2", "", "Final project"),
    showStatus("Sign in to view your project and submission status.")
  );

  window.addEventListener("skillpulse:signed-in", () => {
    signedIn = true;
    load();
  });

  window.addEventListener("skillpulse:modules-changed", () => load());
})();
