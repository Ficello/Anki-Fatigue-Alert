/* Speed Focus Mode for Alerte Fatigue (Anki EDN) */

var faSfmAutoAlertQTimeout = null;
var faSfmAutoAlertATimeout = null;
var faSfmAutoRevealTimeout = null;
var faSfmAutoActionTimeout = null;
var faSfmCurrentTimeout = null;
var faSfmCurrentAction = null;
var faSfmCurrentInterval = null;
var faSfmTimeLeft = 0;

function faSfmReset() {
  if (faSfmCurrentInterval !== null) {
    clearInterval(faSfmCurrentInterval);
    faSfmCurrentInterval = null;
  }
  faSfmCurrentTimeout = null;
  faSfmCurrentAction = null;
}

function faSfmUpdateTime() {
  var timeNode = document.getElementById("faSfmTime");
  if (!timeNode) return;

  if (faSfmTimeLeft <= 0) {
    timeNode.textContent = "";
    return;
  }
  var time = Math.max(faSfmTimeLeft, 0);
  var m = Math.floor(time / 60);
  var s = time % 60;
  if (s < 10) {
    s = "0" + s;
  }
  var actionStr = faSfmCurrentAction ? (faSfmCurrentAction + " ") : "";
  timeNode.textContent = actionStr + m + ":" + s;
  faSfmTimeLeft = time - 1;
}

function faSfmSetCurrentTimer(timeout, action, ms) {
  faSfmReset();
  faSfmCurrentAction = action;
  faSfmCurrentTimeout = timeout;
  faSfmTimeLeft = Math.round(ms / 1000);
  faSfmUpdateTime();
  faSfmCurrentInterval = setInterval(function () {
    faSfmUpdateTime();
  }, 1000);
}

function faSfmClearCurrentTimeout() {
  if (faSfmCurrentTimeout !== null) {
    clearTimeout(faSfmCurrentTimeout);
    faSfmCurrentTimeout = null;
  }
  if (faSfmAutoAlertQTimeout !== null) {
    clearTimeout(faSfmAutoAlertQTimeout);
    faSfmAutoAlertQTimeout = null;
  }
  if (faSfmAutoAlertATimeout !== null) {
    clearTimeout(faSfmAutoAlertATimeout);
    faSfmAutoAlertATimeout = null;
  }
  if (faSfmAutoRevealTimeout !== null) {
    clearTimeout(faSfmAutoRevealTimeout);
    faSfmAutoRevealTimeout = null;
  }
  if (faSfmAutoActionTimeout !== null) {
    clearTimeout(faSfmAutoActionTimeout);
    faSfmAutoActionTimeout = null;
  }
  if (faSfmCurrentInterval !== null) {
    clearInterval(faSfmCurrentInterval);
    faSfmCurrentInterval = null;
  }
  faSfmCurrentAction = null;

  var timeNode = document.getElementById("faSfmTime");
  if (timeNode) {
    timeNode.textContent = window.faSfmLabelStopped || "Arrêté";
  }

  if (typeof pycmd !== "undefined") {
    pycmd("fa_sfm:timer_stopped");
  }
}

function faSfmClearQuestionTimers() {
  if (faSfmAutoAlertQTimeout !== null) {
    clearTimeout(faSfmAutoAlertQTimeout);
    faSfmAutoAlertQTimeout = null;
  }
  if (faSfmAutoRevealTimeout !== null) {
    clearTimeout(faSfmAutoRevealTimeout);
    faSfmAutoRevealTimeout = null;
  }
}

function faSfmClearAnswerTimers() {
  if (faSfmAutoAlertATimeout !== null) {
    clearTimeout(faSfmAutoAlertATimeout);
    faSfmAutoAlertATimeout = null;
  }
  if (faSfmAutoActionTimeout !== null) {
    clearTimeout(faSfmAutoActionTimeout);
    faSfmAutoActionTimeout = null;
  }
}

function faSfmClearAlertQuestion() {
  faSfmClearQuestionTimers();
}

window.faSfmClearQuestionTimers = faSfmClearQuestionTimers;
window.faSfmClearAnswerTimers = faSfmClearAnswerTimers;

function faSfmSetAutoAlertQuestion(ms, sec) {
  faSfmClearAlertQuestion();
  faSfmAutoAlertQTimeout = setTimeout(function () {
    if (typeof pycmd !== "undefined") {
      pycmd("fa_sfm:alert_question:" + sec);
    }
  }, ms);
}

function faSfmSetAutoAlertAnswer(ms, sec, showCountdown) {
  // Ensure any question alert timeout is strictly canceled
  faSfmClearAlertQuestion();
  if (faSfmAutoAlertATimeout !== null) {
    clearTimeout(faSfmAutoAlertATimeout);
  }
  faSfmAutoAlertATimeout = setTimeout(function () {
    if (typeof pycmd !== "undefined") {
      pycmd("fa_sfm:alert_answer:" + sec);
    }
  }, ms);

  if (showCountdown && faSfmCurrentAction === null) {
    var label = window.faSfmLabelReading || "Lecture";
    faSfmSetCurrentTimer(faSfmAutoAlertATimeout, label, ms);
  }
}

function faSfmSetAutoReveal(ms) {
  faSfmReset();
  if (faSfmAutoRevealTimeout !== null) {
    clearTimeout(faSfmAutoRevealTimeout);
  }
  faSfmAutoRevealTimeout = setTimeout(function () {
    if (typeof pycmd !== "undefined") {
      pycmd("ans");
    }
  }, ms);
  var label = window.faSfmLabelReveal || "Réponse";
  faSfmSetCurrentTimer(faSfmAutoRevealTimeout, label, ms);
}

function faSfmSetAutoAction(ms, action) {
  faSfmReset();
  if (faSfmAutoActionTimeout !== null) {
    clearTimeout(faSfmAutoActionTimeout);
  }
  faSfmAutoActionTimeout = setTimeout(function () {
    if (typeof pycmd !== "undefined") {
      pycmd("fa_sfm:action:" + action);
    }
  }, ms);
  faSfmSetCurrentTimer(faSfmAutoActionTimeout, action, ms);
}

function faSfmHide() {
  var el = document.getElementById("faSfmControls");
  if (el) el.style.display = "none";
}

function faSfmShow() {
  var el = document.getElementById("faSfmControls");
  if (el) el.style.display = "";
}

function faSfmInitButton() {
  var existing = document.getElementById("faSfmControls");
  if (existing) {
    existing.remove();
  }
  if (!window.faSfmShowButton) {
    return;
  }
  var middle = document.getElementById("middle");
  if (!middle) {
    setTimeout(faSfmInitButton, 50);
    return;
  }

  var btnTitle = (window.faSfmLabelBtnTitle || "Plus de temps") + 
    (window.faSfmHotkey ? " (" + window.faSfmHotkey.toUpperCase() + ")" : "");
  var btnText = window.faSfmLabelBtnText || "Plus de temps";

  var html = [
    '<td id="faSfmControls" align="center" valign="top" class="stat" style="display:none; padding: 0 4px;">',
    '<button class="fa-sfm-btn" title="' + btnTitle + '" onclick="faSfmClearCurrentTimeout();" ',
    'style="cursor: pointer; padding: 3px 8px; font-size: 11px; border-radius: 4px;">',
    btnText,
    ' <span id="faSfmTime" class="stattxt" style="font-weight: bold; margin-left: 3px;"></span>',
    '</button>',
    '</td>'
  ].join('');

  middle.insertAdjacentHTML("afterend", html);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", faSfmInitButton);
} else {
  faSfmInitButton();
}
