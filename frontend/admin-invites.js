"use strict";

// Admin-only panel for inviting learners, tutors and admins.
// The API creates the Cognito account, which emails a temporary password.
(() => {
  const headers = {
    "Content-Type": "application/json",
    "X-Organization-ID": pilotContext.organizationId
  };

  function field(labelText, input) {
    const label = element("label", "", labelText);
    label.append(input);
    return label;
  }

  function buildPanel() {
    const panel = element("section", "card");
    panel.id = "admin-invites";
    panel.append(
      element("p", "eyebrow", "ADMIN"),
      element("h2", "", "Invite someone to SkillPulse"),
      element(
        "p",
        "",
        "They will receive an email with a temporary password. " +
          "Their account becomes active the first time they sign in."
      )
    );

    const form = document.createElement("form");

    const fullName = document.createElement("input");
    fullName.type = "text";
    fullName.name = "full_name";
    fullName.required = true;
    fullName.maxLength = 150;
    fullName.autocomplete = "off";

    const email = document.createElement("input");
    email.type = "email";
    email.name = "email";
    email.required = true;
    email.maxLength = 254;
    email.autocomplete = "off";

    const role = document.createElement("select");
    role.name = "role";
    [
      ["student", "Learner"],
      ["tutor", "Tutor"],
      ["admin", "Admin"]
    ].forEach(([value, label]) => {
      const option = element("option", "", label);
      option.value = value;
      role.append(option);
    });

    const submit = element("button", "", "Send invitation");
    submit.type = "submit";

    const result = element("p", "notice", "");
    result.setAttribute("role", "status");
    result.setAttribute("aria-live", "polite");
    result.hidden = true;

    form.append(
      field("Full name", fullName),
      field("Email address", email),
      field("Role", role),
      submit
    );
    panel.append(form, result);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      submit.disabled = true;
      result.hidden = false;
      result.textContent = "Sending invitation…";

      try {
        const invited = await window.skillpulseAuth.request("/admin/invitations", {
          method: "POST",
          headers,
          body: JSON.stringify({
            full_name: fullName.value.trim(),
            email: email.value.trim(),
            role: role.value
          })
        });
        result.textContent =
          `Invitation sent to ${invited.email}. ` +
          "Ask them to check their inbox (and spam folder).";
        form.reset();
      } catch (error) {
        result.textContent = `Could not send the invitation: ${error.message}`;
      } finally {
        submit.disabled = false;
      }
    });

    return panel;
  }

  window.addEventListener("skillpulse:signed-in", (event) => {
    const user = event.detail?.user;
    const isAdmin = user?.memberships?.some(
      (membership) =>
        membership.organization_id === pilotContext.organizationId &&
        membership.role === "admin"
    );
    if (!isAdmin || document.getElementById("admin-invites")) return;

    const panel = buildPanel();
    const header = document.querySelector(".workspace-header");
    if (header) header.after(panel);
    else document.querySelector(".workspace")?.prepend(panel);

    const nav = document.querySelector(".sidebar nav");
    if (nav) {
      const link = element("a", "", "Invite people");
      link.href = "#admin-invites";
      nav.prepend(link);
    }
  });
})();
