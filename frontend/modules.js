"use strict";

(() => {
  const container = document.getElementById("learning-path");
  if (!container) return;

  const base = `/catalog/courses/${pilotContext.courseId}` +
    `/cohorts/${pilotContext.cohortId}/my-modules`;

  const headers = {
    "X-Organization-ID": pilotContext.organizationId
  };

  // Draft study outlines for the two existing demo topics.
  const outlines = {
    "41000000-0000-0000-0000-000000000001": coursePreview.topics[0],
    "41000000-0000-0000-0000-000000000002": coursePreview.topics[1]
  };

  const labels = {
    locked: "Locked",
    available: "Available",
    in_progress: "In progress",
    completed: "Completed"
  };

  let busy = false;
  let signedIn = false;

  function message(text) {
    const note = element("p", "notice", text);
    note.setAttribute("role", "status");
    return note;
  }

  function studyOutline(module) {
    const details = element("details", "topic-details");
    const summary = element("summary", "", "View study outline");
    details.append(summary);

    const outline = outlines[module.topic_id];

    if (outline) {
      const objectives = element("ul", "");
      outline.objectives.forEach((objective) => {
        objectives.append(element("li", "", objective));
      });
      details.append(
        element("h4", "", "Learning objectives"),
        objectives,
        element("h4", "", "Practice activity"),
        element("p", "", outline.activity)
      );
    } else {
      details.append(element(
        "p", "", "Study content has not been published for this module."
      ));
    }

    details.append(element(
      "p", "form-note",
      "Draft study content. Opening this outline does not complete " +
      "the module. Use Take module check to demonstrate your understanding."
    ));

    const support = element("a", "", "Need help? Report a learning blocker");
    support.href = "#support";
    details.append(support);

    return details;
  }

  function render(modules, openedTopicId = null) {
    container.replaceChildren();
    container.className = "learning-path";

    const completed = modules.filter(
      (module) => module.status === "completed"
    ).length;

    const overview = element("div", "course-overview");
    overview.append(
      element("span", "badge", "Live module progress · Demo course"),
      element("h3", "", coursePreview.title),
      element(
        "p", "",
        `${completed} of ${modules.length} modules completed`
      ),
      element(
        "p", "form-note",
        "Complete earlier modules to unlock the next. " +
        "Pass each module check to complete it. Certificate checks are not connected yet."
      )
    );

    const refresh = element("button", "", "Refresh modules");
    refresh.type = "button";
    refresh.addEventListener("click", () => {
      if (!busy) loadModules();
    });
    overview.append(refresh);
    container.append(overview);

    if (!modules.length) {
      container.append(message("No modules have been added to this course."));
      return;
    }

    modules.forEach((module) => {
      const card = element("article", "topic-card");
      const heading = element("div", "topic-header");
      const title = element("div", "");

      title.append(
        element("h3", "", module.title),
        element("span", "badge", labels[module.status]),
        element(
          "p", "topic-meta",
          [
            module.expected_hours == null
              ? null
              : `${module.expected_hours} estimated hours`,
            module.exam_domain
          ].filter(Boolean).join(" · ")
        )
      );

      heading.append(
        element(
          "span", "topic-number",
          String(module.sequence_number).padStart(2, "0")
        ),
        title
      );
      card.append(heading);

      if (module.status === "locked") {
        const locked = element("button", "", "Locked");
        locked.type = "button";
        locked.disabled = true;
        card.append(
          locked,
          element(
            "p", "form-note",
            "Complete all earlier modules to unlock this module."
          )
        );
      } else if (module.status === "available") {
        const start = element("button", "", "Start module");
        start.type = "button";
        const status = message("");

        start.addEventListener("click", async () => {
          if (busy) return;
          busy = true;
          start.disabled = true;
          status.textContent = "Starting module…";

          try {
            await window.skillpulseAuth.request(
              `${base}/${encodeURIComponent(module.topic_id)}/start`,
              { method: "POST", headers }
            );
          } catch (error) {
            status.textContent =
              `Could not confirm the module was started: ${error.message}. ` +
              "Refresh modules to check its status.";
            start.disabled = false;
            busy = false;
            return;
          }

          busy = false;
          await loadModules(module.topic_id);
        });

        card.append(start, status);
      } else {
        const details = studyOutline(module);
        const open = element(
          "button", "",
          module.status === "completed" ? "Review module" : "Continue module"
        );
        open.type = "button";
        open.addEventListener("click", () => {
          details.open = true;
          details.querySelector("summary").focus();
          details.scrollIntoView({ behavior: "smooth", block: "nearest" });
        });

        if (module.topic_id === openedTopicId) {
          details.open = true;
        }

        card.append(open, details);
      }

      if (window.skillpulseModuleChecks) {
        window.skillpulseModuleChecks.mount(card, module);
      }
      container.append(card);
    });
  }

  async function loadModules(openedTopicId = null) {
    if (!signedIn || busy) return;
    busy = true;
    container.replaceChildren(message("Loading your modules…"));

    try {
      const modules = await window.skillpulseAuth.request(base, { headers });

      if (
        !Array.isArray(modules) ||
        !modules.every((module) =>
          module &&
          typeof module.topic_id === "string" &&
          Object.hasOwn(labels, module.status)
        )
      ) {
        throw new Error("Unexpected module response");
      }

      render(modules, openedTopicId);
    } catch (error) {
      const retry = element("button", "", "Retry loading modules");
      retry.type = "button";
      retry.addEventListener("click", () => loadModules());
      container.replaceChildren(
        message(`Modules could not be loaded: ${error.message}`),
        retry
      );
    } finally {
      busy = false;
    }
  }

  window.addEventListener("skillpulse:modules-changed", () => {
    loadModules();
  });

  window.addEventListener("skillpulse:signed-in", () => {
    signedIn = true;
    loadModules();
  });
})();
