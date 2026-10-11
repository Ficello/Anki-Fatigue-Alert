/* Speed Focus Mode reviewer handler for Alerte Fatigue (Anki EDN) */

function faSfmOnKeyup() {
  if (typeof pycmd !== "undefined") {
    pycmd("fa_sfm:typeans");
  }
  var typeans = document.getElementById("typeans");
  if (typeans) {
    typeans.removeEventListener("keyup", faSfmOnKeyup);
  }
}

function faSfmBindTypeans() {
  var typeans = document.getElementById("typeans");
  if (typeans) {
    typeans.addEventListener("keyup", faSfmOnKeyup);
  }
}

/* ------------------------------------------------------------------
   Visual Alert: Immersive Call of Duty Low-Health Style Vignette Pulse
   ------------------------------------------------------------------ */

var faSfmAlertTimeout = null;

function faSfmEnsureAlertStyles() {
  var style = document.getElementById("fa-sfm-alert-style");
  if (!style) {
    style = document.createElement("style");
    style.id = "fa-sfm-alert-style";
    document.head.appendChild(style);
  }

  style.textContent = `
    @keyframes faSfmBorderPulse {
      0% {
        opacity: 0;
      }
      45% {
        opacity: 1;
      }
      55% {
        opacity: 1;
      }
      100% {
        opacity: 0;
      }
    }

    #fa-sfm-pulse-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      pointer-events: none;
      z-index: 99998;
      contain: strict;
      transform: translateZ(0);
      -webkit-transform: translateZ(0);
      backface-visibility: hidden;
      -webkit-backface-visibility: hidden;
      will-change: opacity;
      opacity: 0;
    }

    #fa-sfm-pulse-overlay.fa-sfm-type-question {
      background: radial-gradient(
        ellipse at center,
        rgba(0, 0, 0, 0) 65%,
        rgba(195, 75, 60, 0.12) 85%,
        rgba(195, 75, 60, 0.35) 98%
      );
      box-shadow:
        inset 0 0 0 2.5px rgba(210, 90, 75, 0.65),
        inset 0 0 30px rgba(195, 75, 60, 0.3);
    }

    #fa-sfm-pulse-overlay.fa-sfm-type-answer {
      background: radial-gradient(
        ellipse at center,
        rgba(0, 0, 0, 0) 65%,
        rgba(217, 130, 43, 0.12) 85%,
        rgba(217, 130, 43, 0.35) 98%
      );
      box-shadow:
        inset 0 0 0 2.5px rgba(225, 145, 65, 0.65),
        inset 0 0 30px rgba(217, 130, 43, 0.3);
    }

    #fa-sfm-pulse-overlay.fa-sfm-animating {
      animation: faSfmBorderPulse 3.2s ease-in-out forwards;
    }
  `;
}

function faSfmClearAlertVisual() {
  if (faSfmAlertTimeout) {
    clearTimeout(faSfmAlertTimeout);
    faSfmAlertTimeout = null;
  }
  var overlay = document.getElementById("fa-sfm-pulse-overlay");
  if (overlay) {
    overlay.classList.remove("fa-sfm-animating", "fa-sfm-type-question", "fa-sfm-type-answer");
    overlay.className = "";
  }
}

function faSfmTriggerAlertVisual(htmlMsg, alertType, qtOverlayActive) {
  if (faSfmAlertTimeout) {
    clearTimeout(faSfmAlertTimeout);
    faSfmAlertTimeout = null;
  }
  if (qtOverlayActive) {
    faSfmClearAlertVisual();
    return;
  }
  faSfmEnsureAlertStyles();

  var overlay = document.getElementById("fa-sfm-pulse-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "fa-sfm-pulse-overlay";
    document.body.appendChild(overlay);
  }

  var typeClass = (alertType === "answer") ? "fa-sfm-type-answer" : "fa-sfm-type-question";

  // Clean reset of animation state without DOM mutation
  overlay.classList.remove("fa-sfm-animating", "fa-sfm-type-question", "fa-sfm-type-answer");
  overlay.className = typeClass;

  // Double rAF ensures the compositor sees the class change and triggers the animation smoothly
  requestAnimationFrame(function () {
    requestAnimationFrame(function () {
      overlay.classList.add("fa-sfm-animating");
    });
  });

  faSfmAlertTimeout = setTimeout(function () {
    faSfmClearAlertVisual();
  }, 3300);
}

// Expose globally
window.faSfmTriggerAlertVisual = faSfmTriggerAlertVisual;
window.faSfmClearAlertVisual = faSfmClearAlertVisual;

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", function () {
    setTimeout(faSfmBindTypeans, 150);
  });
} else {
  setTimeout(faSfmBindTypeans, 150);
}
