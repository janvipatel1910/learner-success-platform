"use strict";

(() => {
  const domain =
    "https:" + "//eu-west-2wvizwj4bd.auth.eu-west-2.amazoncognito.com";
  const clientId = "7nqmgj00fja4vkcr0in7lj4oja";
  // Local development uses the Vite dev server and the local API;
  // the deployed site serves the API from the same CloudFront address.
  const isLocal = ["localhost", "127.0.0.1"].includes(location.hostname);
  const redirectUri = location.origin + "/";
  const apiBase = isLocal
    ? "http:" + "//localhost:8000/api/v1"
    : location.origin + "/api/v1";
  const storageKey = "skillpulse-login";
  const status = document.getElementById("login-status");
  const account = document.querySelector(".account-status");

  let accessToken = null;
  let expiresAt = 0;

  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Sign in";
  button.style.marginTop = "0";
  const loginPage = document.getElementById("login-page");
  const loginActions = document.getElementById("login-actions");
  const appShell = document.querySelector(".app-shell");

  function setSignedInView(isSignedIn) {
    loginPage.hidden = isSignedIn;
    appShell.hidden = !isSignedIn;

    if (isSignedIn) {
      account.after(button);
    } else {
      button.textContent = "Sign in";
      loginActions.append(button);
    }
  }

  loginActions.append(button);
  setSignedInView(false);

  function encode(bytes) {
    return btoa(String.fromCharCode(...bytes))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  }

  function randomValue() {
    return encode(crypto.getRandomValues(new Uint8Array(32)));
  }

  async function signIn() {
    const verifier = randomValue();
    const state = randomValue();
    const digest = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(verifier)
    );

    sessionStorage.setItem(storageKey, JSON.stringify({
      verifier,
      state,
      createdAt: Date.now()
    }));

    const url = new URL(domain + "/oauth2/authorize");
    url.search = new URLSearchParams({
      client_id: clientId,
      response_type: "code",
      redirect_uri: redirectUri,
      scope: "openid email",
      state,
      code_challenge: encode(new Uint8Array(digest)),
      code_challenge_method: "S256"
    }).toString();

    location.assign(url.href);
  }

  function signOut() {
    accessToken = null;
    expiresAt = 0;
    sessionStorage.removeItem(storageKey);
    setSignedInView(false);

    const url = new URL(domain + "/logout");
    url.search = new URLSearchParams({
      client_id: clientId,
      logout_uri: redirectUri
    }).toString();

    location.assign(url.href);
  }

  async function request(path, options = {}) {
    if (!path.startsWith("/") || path.startsWith("//")) {
      throw new Error("Invalid API path.");
    }
    if (!accessToken || Date.now() >= expiresAt) {
      throw new Error("Please sign in again.");
    }

    const headers = new Headers(options.headers);
    headers.set("Authorization", `Bearer ${accessToken}`);

    const response = await fetch(apiBase + path, {
      ...options,
      headers,
      redirect: "error"
    });

    if (!response.ok) {
      if (response.status === 401) {
        accessToken = null;
        expiresAt = 0;
        account.textContent = "Session expired";
        setSignedInView(false);
      }

      let message = `API request failed (${response.status}).`;
      try {
        const payload = await response.clone().json();
        if (typeof payload.detail === "string") {
          message = payload.detail;
        } else if (Array.isArray(payload.detail)) {
          message = payload.detail
            .map((item) => item.msg || JSON.stringify(item))
            .join("; ");
        }
      } catch {
        // Keep the generic message if the response has no JSON detail.
      }
      const error = new Error(message);
      error.status = response.status;
      throw error;

    }

    return response.status === 204 ? null : response.json();
  }

  // Other dashboard code can call the API without reading the token.
  window.skillpulseAuth = { request };

  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      if (accessToken) {
        signOut();
      } else {
        await signIn();
      }
    } catch (error) {
      status.textContent = error.message;
      button.disabled = false;
    }
  });

  async function finishLogin() {
    const params = new URLSearchParams(location.search);
    if (!params.has("code") && !params.has("error")) return;

    const saved = sessionStorage.getItem(storageKey);
    sessionStorage.removeItem(storageKey);

    // Remove the authorization code from the address bar immediately.
    history.replaceState({}, "", location.pathname);

    if (params.has("error")) {
      throw new Error("Sign-in was not completed. Please try again.");
    }

    const pending = saved ? JSON.parse(saved) : null;
    if (
      !pending ||
      !pending.state ||
      !pending.verifier ||
      pending.state !== params.get("state") ||
      !Number.isFinite(pending.createdAt) ||
      Date.now() - pending.createdAt > 15 * 60 * 1000
    ) {
      throw new Error("Login request expired or did not match. Sign in again.");
    }

    status.textContent = "Completing sign-in…";
    button.disabled = true;

    const response = await fetch(domain + "/oauth2/token", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded"
      },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        client_id: clientId,
        redirect_uri: redirectUri,
        code: params.get("code"),
        code_verifier: pending.verifier
      })
    });

    if (!response.ok) {
      throw new Error("Could not complete sign-in. Please try again.");
    }

    const tokens = await response.json();
    const lifetime = Number(tokens.expires_in);

    if (
      typeof tokens.access_token !== "string" ||
      !Number.isFinite(lifetime) ||
      lifetime <= 0
    ) {
      throw new Error("Invalid login response. Please sign in again.");
    }

    accessToken = tokens.access_token;
    expiresAt = Date.now() + lifetime * 1000;
    const user = await request("/auth/me");
    setSignedInView(true);
    button.textContent = "Sign out";
    account.textContent = user.full_name;
    status.textContent =
      `Signed in as ${user.full_name}. Learning data connection is next.`;

    window.dispatchEvent(new CustomEvent("skillpulse:signed-in", {
      detail: { user }
    }));
  }

  finishLogin()
    .catch((error) => {
      status.textContent = error.message;
    })
    .finally(() => {
      button.disabled = false;
    });
})();
