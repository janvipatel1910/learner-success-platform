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

