"use strict";

(() => {
  const projectSection = document.getElementById("final-project");
  if (!projectSection) return;

  const section = document.createElement("section");
  section.id = "certificate-status";
  section.className = "card";
  section.style.marginTop = "24px";
  section.setAttribute("aria-live", "polite");
  projectSection.after(section);

  const labels = {
    attendance_met: "Attendance requirement",
    assignment_met: "Assignment requirement",
    lab_met: "Lab completion requirement",
    mock_score_met: "Mock exam requirement",
    blockers_cleared: "Learning blockers resolved",
    module_checks_met: "All module tests passed",
    final_project_met: "Final project passed"
  };

  function showMessage(message) {
    section.replaceChildren();
    section.append(
      document.createElement("h2"),
      document.createElement("p")
    );
    section.querySelector("h2").textContent = "Certificate eligibility";
    section.querySelector("p").textContent = message;
  }

  window.addEventListener("skillpulse:signed-in", async (event) => {
    const user = event.detail?.user;
    const membership = user?.memberships?.find(
      (item) =>
        item.organization_id === pilotContext.organizationId &&
        item.role === "student"
    );

    if (!membership) {
      section.hidden = true;
      return;
    }

    section.hidden = false;
    showMessage("Checking your certificate requirements…");

    try {
      const result = await window.skillpulseAuth.request(
        `/catalog/courses/${pilotContext.courseId}` +
          `/cohorts/${pilotContext.cohortId}` +
          "/certificate-eligibility/me/evaluate",
        {
          method: "POST",
          headers: {
            "X-Organization-ID": pilotContext.organizationId
          }
        }
      );

      section.replaceChildren();
      section.append(
        document.createElement("p"),
        document.createElement("h2"),
        document.createElement("p")
      );
      section.querySelector("p").textContent = "CERTIFICATE";
      section.querySelector("h2").textContent = result.is_eligible
        ? "You meet the certificate requirements"
        : "Certificate requirements in progress";
      section.querySelectorAll("p")[1].textContent = result.is_eligible
        ? "Your eligibility is confirmed. Certificate download is not available yet."
        : "Complete the requirements below, then check your eligibility again.";

      const list = document.createElement("ul");
      for (const [key, label] of Object.entries(labels)) {
        const item = document.createElement("li");
        item.textContent = `${result[key] ? "✓ Met" : "• Not met"} — ${label}`;
        list.append(item);
      }
      section.append(list);

      if (result.is_eligible) {
        const issueButton = document.createElement("button");
        issueButton.type = "button";
        issueButton.textContent = "Issue my certificate";

        issueButton.addEventListener("click", async () => {
          issueButton.disabled = true;
          issueButton.textContent = "Issuing certificate…";

          try {
            const certificate = await window.skillpulseAuth.request(
              `/catalog/courses/${pilotContext.courseId}` +
                `/cohorts/${pilotContext.cohortId}/certificates/me/issue`,
              {
                method: "POST",
                headers: {
                  "X-Organization-ID": pilotContext.organizationId
                }
              }
            );

            const issued = document.createElement("div");
            issued.className = "course-overview";
            issued.append(
              document.createElement("h3"),
              document.createElement("p"),
              document.createElement("p")
            );
            issued.querySelector("h3").textContent =
              certificate.certification_name;
            issued.querySelectorAll("p")[0].textContent =
              `Awarded to ${certificate.learner_name}`;
            issued.querySelectorAll("p")[1].textContent =
              `Certificate number: ${certificate.certificate_number}`;

            const viewUrl = new URL("certificate-view.html", window.location.href);
            viewUrl.searchParams.set("number", certificate.certificate_number);

            const verify = document.createElement("a");
            verify.textContent = "View and print certificate";
            verify.href = viewUrl.href;
            verify.target = "_blank";
            verify.rel = "noopener noreferrer";
            issued.append(verify);
            section.append(issued);
            issueButton.remove();
          } catch (issueError) {
            issueButton.disabled = false;
            issueButton.textContent = "Issue my certificate";
            showMessage(
              `Certificate could not be issued: ${issueError.message}`
            );
          }
        });

        section.append(issueButton);
      }
    } catch (error) {
      showMessage(`Certificate eligibility could not be checked: ${error.message}`);
    }
  });
})();
