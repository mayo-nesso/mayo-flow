#!/usr/bin/env python3
"""
render.py — render a structured "interactive understanding" spec into a
self-contained, dark-mode HTML page with gated per-section quizzes.

Used by the `mayo-interactive-understanding-html` skill: content sections
that unlock in order, each followed by a 3-question quiz you must answer
correctly (retrying on wrong picks) before the next section reveals itself.

Why this exists: the CSS, quiz/gating JavaScript, and page scaffolding are
identical across every invocation — only the content (prose, diagrams, quiz
questions) changes. This script takes a small JSON spec with just the content
and renders the final page, so the LLM only writes prose and quiz questions,
never boilerplate.

Usage:
    python render.py spec.json [-o output.html]

If -o is omitted, writes to ~/sDeveloper/Docs/YYYY-MM-DD-<slug>.html.

Spec format (JSON):
{
  "title": "From Task to TaskCompletionSource",
  "subtitle": "Why your await hangs forever.",
  "slug": "task-tcs",
  "favicon": "⏳",  // optional, one emoji loosely related to the topic; defaults to a brain
  "sections": [
    {
      "id": "intuition",
      "num": "★",
      "heading": "Intuition — the first principles",
      "lead": "Before the details: this is what you need to know by heart.",
      "html": "<p>...</p><div class=\\"callout\\">...</div>",
      "quiz": [
        {
          "level": "easy",
          "question": "...",
          "options": [
            {"text": "...", "correct": false},
            {"text": "...", "correct": true},
            {"text": "...", "correct": false}
          ],
          "explain": "..."
        },
        { "level": "medium", ... },
        { "level": "hard", ... }
      ]
    }
  ],
  "ui": {}  // optional, see LANGUAGE / UI TEXT below — only needed for a non-English page
}

Optional "review" key on a section (use it when the target is a PR, branch or diff):
  "review": {
    "verdict": "good|ok|bad",          // looks good / okay with notes / needs changes
    "summary": "One or two sentences: the evaluator's take on this section's code.",
    "items": [ {"tag": "good|warn|bad|nit|question", "area": "Security", "text": "..."} ]
  }
It renders a "Reviewer's take" card after the section's content and before its quiz.
`area` is free text, for example Design, Logic, Security, Performance, Tests, Style.

Rules enforced by this script:
- Every section with a "quiz" key must have EXACTLY 3 questions (easy/medium/hard
  is the intended shape, but the level strings are free text — "facil"/"media"/
  "dificil" work equally well and drive the same three badge colors via a
  simple keyword match).
- A section with no "quiz" key is never gated and never gates the next section
  (use this for a pure closing/summary section).
- Option order within each question is shuffled at render time — write options
  in whatever order reads naturally in the spec.
- Quiz cards are rendered as static HTML at build time (not injected by JS on
  load), so questions are visible even in contexts that don't execute
  JavaScript (iOS Quick Look, WhatsApp/Drive/Telegram in-app previews, etc.).
  JS only adds interactivity (click handling, gating, persisted progress) on
  top of markup that's already there.
- Option TEXT LENGTH is checked as a proxy for the classic "the correct answer
  is always the longest/most-hedged one" tell. This script prints warnings
  (not a hard failure) to stderr; re-read them and rebalance the spec before
  handing off the page.

LANGUAGE / UI TEXT: the page's chrome (quiz prompt, continue button, lock
overlay, progress counter, reset confirm, footer, <html lang>) defaults to
English. Only override it — with an optional top-level "ui" object in the
spec — when the page itself is being written in another language; every key
is optional and falls back to its English default. Keys: html_lang,
quiz_prompt, continue_btn, reading_time ("{minutes}" is replaced), wrong_feedback, progress_done_word, reset_label,
reset_confirm, lock_text (gets the gate section's heading substituted for
"{heading}"), lock_link, footer_text, review_title, verdict_good, verdict_ok,
verdict_bad, tag_good, tag_warn, tag_bad, tag_nit, tag_question.
"""
import argparse
import datetime
import json
import random
import re
import sys
import urllib.parse
from pathlib import Path

CSS = """
  :root{
    --bg:#0f1115; --bg2:#161922; --panel:#1b1f2a; --panel2:#20242f;
    --text:#e7e9ee; --muted:#9aa3b2; --border:#2a2f3d;
    --accent:#6ea8fe; --accent2:#a78bfa;
    --easy:#3ecf8e; --medium:#e8b93b; --hard:#f0556b;
    --code-bg:#11141b;
  }
  *{box-sizing:border-box;}
  body{
    margin:0; background:var(--bg); color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    line-height:1.6;
  }
  .wrap{max-width:1180px; margin:0 auto; padding:0 12px 120px;}

  #global-progress-bar{position:sticky; top:0; z-index:50; height:4px; background:var(--border);}
  #global-progress-fill{height:100%; width:0%; background:linear-gradient(90deg,var(--accent),var(--accent2)); transition:width .4s;}
  #progress-readout{
    position:fixed; top:12px; right:16px; z-index:50; font-size:.72rem; color:var(--muted);
    background:var(--panel); border:1px solid var(--border); padding:5px 12px; border-radius:999px;
    display:flex; align-items:center; gap:8px;
  }
  .reset-btn{
    background:none; border:none; color:var(--muted); cursor:pointer; font-size:.9rem;
    padding:0; line-height:1; font-family:inherit;
  }
  .reset-btn:hover{color:var(--text);}

  header.hero{
    padding:64px 24px 40px; text-align:center;
    background:linear-gradient(180deg,var(--bg2),var(--bg));
    border-bottom:1px solid var(--border);
  }
  header.hero h1{
    font-size:2.1rem; margin:0 0 10px; letter-spacing:-.02em;
    background:linear-gradient(90deg,var(--accent),var(--accent2));
    -webkit-background-clip:text; background-clip:text; color:transparent;
  }
  header.hero p{color:var(--muted); max-width:640px; margin:0 auto; font-size:1.02rem;}
  .read-time{margin:12px 0 0; font-size:.85rem; color:var(--muted);}
  nav.toc{display:flex; flex-wrap:wrap; gap:8px; justify-content:center; margin-top:24px;}
  nav.toc a{
    font-size:.8rem; color:var(--muted); text-decoration:none;
    padding:6px 12px; border:1px solid var(--border); border-radius:999px; transition:.15s;
  }
  nav.toc a:hover{color:var(--text); border-color:var(--accent);}
  nav.toc a.done{color:var(--easy); border-color:var(--easy);}
  nav.toc a.done::before{content:"\\2713 ";}

  section{padding:48px 0; border-bottom:1px solid var(--border); position:relative;}
  section:last-of-type{border-bottom:none;}
  section h2{font-size:1.4rem; margin:0 0 6px; display:flex; align-items:center; gap:10px;}
  section.locked h2{opacity:.45;}
  section h2 .num{
    font-size:.75rem; color:var(--bg); background:var(--accent); width:26px; height:26px;
    border-radius:50%; display:flex; align-items:center; justify-content:center; flex-shrink:0;
  }
  section .lead{color:var(--muted); margin:0 0 22px; font-size:.98rem;}
  p{margin:0 0 14px;}
  strong{color:var(--text);}
  code{
    background:var(--code-bg); padding:2px 6px; border-radius:5px;
    font-family:"SF Mono",Menlo,Consolas,monospace; font-size:.88em; border:1px solid var(--border);
  }
  pre{
    background:var(--code-bg); border:1px solid var(--border); border-radius:10px;
    padding:16px 18px; overflow-x:auto; font-size:.85rem; margin:0 0 16px; white-space:pre;
    font-family:"SF Mono",Menlo,Consolas,monospace; line-height:1.55;
  }
  pre code{background:none; border:none; padding:0; font-size:1em;}
  /* Code and comment grid: one row per code line. Built from <pre><code> blocks that have // comments. */
  .cg{display:grid; grid-template-columns:minmax(0,1.25fr) minmax(0,1fr); background:var(--code-bg);
      border:1px solid var(--border); border-radius:10px; overflow:hidden; margin:0 0 16px;
      font-family:"SF Mono",Menlo,Consolas,monospace; font-size:.84rem; line-height:1.55;}
  .cg .h{padding:6px 14px; background:var(--panel); color:var(--muted); font-size:.7rem; letter-spacing:.06em;
         text-transform:uppercase; border-bottom:1px solid var(--border);}
  .cg .h + .h{border-left:1px solid var(--border);}
  .cg .h .fn{color:var(--text); text-transform:none; letter-spacing:0; font-size:.78rem; margin-left:6px;}
  .cg .r{display:contents;}
  .cg .c, .cg .n{padding:2px 14px; border-left:3px solid transparent;}
  .cg .c{white-space:pre-wrap; overflow-wrap:anywhere;}
  .cg .n{border-left:1px solid var(--border); color:var(--muted); font-size:.8rem;
         font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
  .cg .n.has{color:var(--text);}
  .cg .n.has::before{content:"\u25B8"; color:var(--accent); margin-right:8px; font-size:.7rem;}
  .cg .add{background:rgba(62,207,142,.14);} .cg .c.add{border-left-color:var(--easy);}
  .cg .del{background:rgba(240,85,107,.14); opacity:.85;} .cg .c.del{border-left-color:var(--hard);}
  .cg .r:hover > .c, .cg .r:hover > .n{background:rgba(110,168,254,.12);}
  pre .line-add, pre .line-del{display:block; margin:0 -18px; padding:0 15px; border-left:3px solid transparent;}
  pre .line-add{background:rgba(62,207,142,.14); border-left-color:var(--easy);}
  pre .line-del{background:rgba(240,85,107,.14); border-left-color:var(--hard); opacity:.85;}
  table{border-collapse:collapse; width:100%; min-width:480px; font-size:.92rem;}
  th, td{border:1px solid var(--border); padding:.5rem .7rem; text-align:left;}
  th{background:var(--panel2);}
  .table-scroll{overflow-x:auto; margin:1rem 0; -webkit-overflow-scrolling:touch;}
  img{max-width:100%; height:auto;}

  .callout{border-left:3px solid var(--accent); background:var(--panel2); padding:12px 16px; border-radius:0 8px 8px 0; margin:16px 0; font-size:.92rem;}
  .callout.warn{border-left-color:var(--hard);}
  .callout.ok{border-left-color:var(--easy);}

  .review{margin:22px 0 8px; border:1px solid var(--border); border-left:4px solid var(--accent); border-radius:0 12px 12px 0; background:var(--panel); padding:16px 18px;}
  .review.good{border-left-color:var(--easy);} .review.ok{border-left-color:var(--medium);} .review.bad{border-left-color:var(--hard);}
  .review-head{display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:8px;}
  .review-title{font-weight:700; font-size:.95rem;}
  .verdict{font-size:.7rem; font-weight:800; text-transform:uppercase; letter-spacing:.05em; padding:3px 10px; border-radius:999px; border:1px solid;}
  .verdict.good{color:var(--easy); border-color:var(--easy); background:rgba(62,207,142,.1);}
  .verdict.ok{color:var(--medium); border-color:var(--medium); background:rgba(232,185,59,.1);}
  .verdict.bad{color:var(--hard); border-color:var(--hard); background:rgba(240,85,107,.1);}
  .review-summary{margin:0 0 12px; font-size:.92rem;}
  .review-items{list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:8px;}
  .review-item{display:flex; gap:10px; align-items:flex-start; font-size:.88rem; color:var(--muted);}
  .review-item .rtag{flex-shrink:0; min-width:78px; text-align:center; font-size:.66rem; font-weight:800; text-transform:uppercase; letter-spacing:.04em; padding:3px 8px; border-radius:6px; border:1px solid;}
  .rtag.good{color:var(--easy); border-color:var(--easy);} .rtag.warn{color:var(--medium); border-color:var(--medium);}
  .rtag.bad{color:var(--hard); border-color:var(--hard);} .rtag.nit,.rtag.question{color:var(--muted); border-color:var(--border);}
  .review-item .rarea{color:var(--text); font-weight:600;}

  .principios{display:flex; flex-direction:column; gap:12px; margin:20px 0;}
  .principio{display:flex; gap:14px; background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:16px 18px;}
  .principio .pnum{font-size:1.1rem; font-weight:800; color:var(--accent); flex-shrink:0; width:26px;}
  .principio h4{margin:0 0 4px; font-size:.95rem;}
  .principio p{margin:0; font-size:.88rem; color:var(--muted);}

  .diagram{background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:1.2rem; margin:1.2rem 0;}
  .flow{display:flex; align-items:center; gap:.6rem; flex-wrap:wrap; justify-content:center; padding:.5rem 0;}
  .box{border:2px solid var(--accent); border-radius:8px; padding:.6rem 1rem; background:var(--panel2); text-align:center; min-width:120px;}
  .box.fail{border-color:var(--hard);}
  .arrow{font-size:1.4rem; color:var(--muted);}

  .glossary{display:flex; flex-direction:column; gap:10px; margin:20px 0;}
  .gterm{background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:12px 16px;}
  .gterm.invented{border-style:dashed; border-color:var(--medium);}
  .gname{font-family:"SF Mono",Menlo,Consolas,monospace; font-size:.88rem; color:var(--accent); margin-bottom:4px; display:flex; align-items:center; gap:8px; flex-wrap:wrap;}
  .gterm.invented .gname{color:var(--medium);}
  .gtag{font-size:.65rem; text-transform:uppercase; letter-spacing:.03em; color:var(--muted); background:var(--panel2); border:1px solid var(--border); padding:2px 7px; border-radius:999px; font-family:inherit;}
  .gdef{font-size:.88rem; color:var(--muted); margin:0;}

  .timeline{background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:1.4rem 1.2rem 1.2rem; margin:1.4rem 0;}
  .timeline-grid{display:grid; grid-template-columns:min-content 1fr; column-gap:14px; row-gap:20px; position:relative;}
  .timeline-ruler{grid-column:2; position:relative; height:20px;}
  .timeline-ruler::before{content:""; position:absolute; top:8px; left:0; right:0; height:4px; background:var(--border); border-radius:999px;}
  .timeline-fill{position:absolute; top:8px; left:0; height:4px; width:0%; border-radius:999px; background:linear-gradient(90deg,#e8b93b,rgba(232,185,59,.25)); transition:width .12s linear;}
  .timeline-slider{position:absolute; top:0; left:0; width:100%; height:20px; margin:0; background:transparent; -webkit-appearance:none; appearance:none; cursor:grab; z-index:3;}
  .timeline-slider:active{cursor:grabbing;}
  .timeline-slider::-webkit-slider-runnable-track{background:transparent; height:20px;}
  .timeline-slider::-moz-range-track{background:transparent; height:20px;}
  .timeline-slider::-webkit-slider-thumb{-webkit-appearance:none; appearance:none; width:18px; height:18px; margin-top:1px; border-radius:50%; background:var(--medium); border:3px solid var(--bg); box-shadow:0 0 0 2px var(--medium); cursor:grab;}
  .timeline-slider::-moz-range-thumb{width:18px; height:18px; border-radius:50%; background:var(--medium); border:3px solid var(--bg); box-shadow:0 0 0 2px var(--medium); cursor:grab;}
  .timeline-now{grid-column:2; grid-row:1 / -1; position:relative; pointer-events:none;}
  .timeline-now-line{position:absolute; top:0; bottom:0; left:0%; width:2px; background:rgba(232,185,59,.5); transition:left .12s linear;}
  .timeline-link-line{position:absolute; top:0; left:0; height:2px; width:0; transform-origin:0 50%; border-radius:999px; pointer-events:none; z-index:0;}
  .timeline-lane-label{grid-column:1; font-size:.76rem; color:var(--muted); display:flex; align-items:center; white-space:nowrap;}
  .timeline-lane-row{grid-column:2; position:relative; height:56px;}
  .timeline-lane-track{position:absolute; top:6px; left:0; width:0%; height:3px; border-radius:999px; background:var(--border);}
  .timeline-node{position:absolute; top:0; transform:translateX(-50%); display:flex; flex-direction:column; align-items:center; gap:6px; width:112px; text-align:center; pointer-events:none;}
  .timeline-dot{width:14px; height:14px; border-radius:50%; background:var(--panel2); border:2px solid var(--border); transition:background-color .12s linear, border-color .12s linear, box-shadow .12s linear;}
  .timeline-label{font-size:.76rem; color:var(--muted); transition:color .12s linear; line-height:1.3;}
  .timeline-label small{display:block; color:var(--muted); font-size:.86em; margin-top:2px;}
  .timeline-controls{display:flex; align-items:center; justify-content:center; gap:12px; margin-top:14px;}
  .timeline-readout{font-size:.85rem; color:var(--text); min-width:110px; text-align:center;}

  .lock-overlay{
    display:none; flex-direction:column; align-items:center; gap:12px; text-align:center;
    padding:40px 20px; border:1px dashed var(--border); border-radius:12px; color:var(--muted);
  }
  section.locked .sec-body{display:none;}
  section.locked .lock-overlay{display:flex;}
  .lock-overlay .lock-icon{font-size:2rem;}
  button.btn{
    background:var(--accent); color:#0b0d12; border:none; padding:9px 16px; border-radius:8px;
    font-size:.85rem; cursor:pointer; font-weight:600; transition:.15s; font-family:inherit;
  }
  button.btn:hover{filter:brightness(1.1);}
  button.btn.secondary{background:var(--panel2); color:var(--text); border:1px solid var(--border);}
  button.btn:disabled{opacity:.4; cursor:not-allowed;}

  .modal-backdrop{
    display:none; position:fixed; inset:0; z-index:100; background:rgba(0,0,0,.6);
    align-items:center; justify-content:center; padding:20px;
  }
  .modal-backdrop.open{display:flex;}
  .modal{
    background:var(--panel); border:1px solid var(--border); border-radius:12px;
    padding:24px; max-width:340px; width:100%; text-align:center;
  }
  .modal p{margin:0 0 20px; color:var(--text); font-size:.92rem;}
  .modal-actions{display:flex; gap:10px; justify-content:center;}

  .quiz-block{margin-top:32px; padding-top:24px; border-top:1px dashed var(--border);}
  .quiz-head{font-size:.95rem; font-weight:700; margin-bottom:14px;}
  .qcard{background:var(--panel); border:1px solid var(--border); border-radius:12px; padding:14px 16px; margin-bottom:12px; transition:border-color .2s;}
  .qcard.shake{animation:shake .4s;}
  @keyframes shake{0%,100%{transform:translateX(0);}25%{transform:translateX(-6px);}75%{transform:translateX(6px);}}
  .qcard.solved{border-color:var(--easy);}
  .qcard-head{display:flex; align-items:baseline; gap:10px; margin-bottom:10px;}
  .level-badge{font-size:.65rem; font-weight:700; padding:3px 8px; border-radius:999px; flex-shrink:0; text-transform:uppercase; letter-spacing:.03em; white-space:nowrap;}
  .level-badge.easy{background:rgba(62,207,142,.15); color:var(--easy);}
  .level-badge.medium{background:rgba(232,185,59,.15); color:var(--medium);}
  .level-badge.hard{background:rgba(240,85,107,.15); color:var(--hard);}
  .qtext{font-size:.92rem; color:var(--text); font-weight:500;}
  .options{display:flex; flex-direction:column; gap:6px;}
  .opt{
    text-align:left; background:var(--panel2); border:1px solid var(--border); color:var(--text);
    padding:8px 12px; border-radius:8px; font-size:.85rem; cursor:pointer; font-family:inherit; transition:.15s;
  }
  .opt:hover:not(:disabled){border-color:var(--accent);}
  .opt.correct{border-color:var(--easy); background:rgba(62,207,142,.15); color:var(--easy);}
  .opt.wrong{border-color:var(--hard); background:rgba(240,85,107,.15); color:var(--hard);}
  .opt:disabled{cursor:default;}
  .qfeedback{font-size:.8rem; margin-top:8px; min-height:1.2em;}
  .qfeedback.good{color:var(--easy);}
  .qfeedback.bad{color:var(--hard);}
  .continue-btn{margin-top:6px;}

  footer{text-align:center; color:var(--muted); font-size:.8rem; padding:40px 0;}
  @media (max-width:640px){
    .cg{grid-template-columns:1fr;} .cg .h:nth-child(2){display:none;}
    .cg .n{border-left:3px solid transparent; padding:0 14px 4px 30px; font-size:.76rem;}
    .cg .n:not(.has){display:none;}
    .wrap{padding:0 10px 100px;}
    header.hero{padding:52px 16px 28px;}
    header.hero h1{font-size:1.5rem;}
    header.hero p{font-size:.92rem;}
    #progress-readout{top:auto; bottom:12px; right:12px; font-size:.68rem; padding:4px 10px;}
    .flow{flex-direction:column;}
    .flow .arrow{transform:rotate(90deg);}
    .qcard-head{flex-wrap:wrap;}
    button.btn{padding:11px 16px;}
    .opt{padding:11px 12px;}
    .timeline-node{width:78px; font-size:.68rem;}
    .timeline-grid{grid-template-columns:78px 1fr; column-gap:8px;}
    .timeline-lane-row{height:64px;}
  }
"""

DEFAULT_UI = {
    "html_lang": "en",
    "quiz_prompt": "To continue, answer these 3 questions",
    "continue_btn": "Continue →",
    "reading_time": "{minutes} min read",
    "wrong_feedback": "Not quite — try again.",
    "progress_done_word": "done",
    "reset_label": "Reset progress",
    "reset_confirm": "Reset all progress on this page?",
    "reset_confirm_btn": "Reset",
    "reset_cancel_btn": "Cancel",
    "unlock_all_label": "Unlock all sections",
    "lock_text": 'Answer the "{heading}" quiz to unlock this section.',
    "lock_link": "↑ Go to the previous section",
    "footer_text": "The end.",
    "review_title": "Reviewer's take",
    "verdict_good": "Looks good",
    "verdict_ok": "Okay, with notes",
    "verdict_bad": "Needs changes",
    "tag_good": "Good",
    "tag_warn": "Consider",
    "tag_bad": "Change",
    "tag_nit": "Nit",
    "tag_question": "Question",
}


def js_str(text: str) -> str:
    """Escape text for embedding inside an existing single-quoted JS string literal."""
    return text.replace("\\", "\\\\").replace("'", "\\'")


JS_ENGINE = """
let completed = new Set();
const STORE_KEY = 'iuh-progress-' + SPEC_SLUG;
try {
  const raw = localStorage.getItem(STORE_KEY);
  if (raw) completed = new Set(JSON.parse(raw));
} catch(e) {}

function saveProgress(){
  try { localStorage.setItem(STORE_KEY, JSON.stringify([...completed])); } catch(e) {}
}

function sectionDone(sec){
  return !sec.quiz || completed.has(sec.id);
}

// Quiz markup already exists in the page (rendered server-side so it shows
// up even without JS running) — this only applies previously-saved state
// on top of it: mark solved cards, disable their buttons, reveal explains.
function hydrateProgress(){
  SECTIONS.forEach(sec=>{
    if (!sec.quiz || !completed.has(sec.id)) return;
    sec.quiz.forEach((q,qi)=>{
      const card = document.querySelector('.qcard[data-sec="'+sec.id+'"][data-qi="'+qi+'"]');
      if (!card) return;
      const correctIdx = q.options.findIndex(o=>o.correct);
      card.classList.add('solved');
      card.querySelectorAll('.opt').forEach((b,i)=>{ b.disabled = true; if (i===correctIdx) b.classList.add('correct'); });
      const feedback = card.querySelector('.qfeedback');
      if (feedback){ feedback.className = 'qfeedback good'; feedback.innerHTML = '\\u2714 ' + q.explain; }
    });
    const cb = document.querySelector('.continue-btn[data-sec="'+sec.id+'"]');
    if (cb) cb.disabled = false;
  });
}

function unlockAllSections(){
  SECTIONS.forEach(sec=>{ if (sec.quiz) completed.add(sec.id); });
  saveProgress();
  hydrateProgress();
  updateGates();
}

// Artifacts render in a sandboxed iframe with no allow-modals, so window.confirm()
// is silently ignored (always resolves falsy) instead of showing a dialog. A plain
// click handler gated on confirm() would look wired up but never actually fire.
// An in-page modal sidesteps native dialogs entirely.
function openResetModal(){
  document.getElementById('reset-modal-backdrop').classList.add('open');
}

function closeResetModal(){
  document.getElementById('reset-modal-backdrop').classList.remove('open');
}

function resetProgress(){
  completed = new Set();
  try { localStorage.removeItem(STORE_KEY); } catch(e) {}
  Object.keys(answeredState).forEach(k=>delete answeredState[k]);
  document.querySelectorAll('.qcard').forEach(card=>{
    card.classList.remove('solved');
    card.querySelectorAll('.opt').forEach(b=>{ b.disabled = false; b.classList.remove('correct','wrong'); });
    const feedback = card.querySelector('.qfeedback');
    if (feedback){ feedback.className = 'qfeedback'; feedback.textContent = ''; }
  });
  document.querySelectorAll('.continue-btn').forEach(b=>{ b.disabled = true; });
  updateGates();
  window.scrollTo({top:0, behavior:'smooth'});
}

const answeredState = {};

function handleOption(btn){
  const card = btn.closest('.qcard');
  if (card.classList.contains('solved')) return;
  const secId = card.dataset.sec, qi = +card.dataset.qi;
  const sec = SECTIONS.find(s=>s.id===secId);
  const q = sec.quiz[qi];
  const oi = +btn.dataset.oi;
  const feedback = card.querySelector('.qfeedback');
  if (q.options[oi].correct){
    card.classList.add('solved');
    card.querySelectorAll('.opt').forEach((b,i)=>{ b.disabled = true; if (i===oi) b.classList.add('correct'); });
    feedback.className = 'qfeedback good';
    feedback.innerHTML = '\\u2714 ' + q.explain;   // HTML, like question and options
    answeredState[secId] = answeredState[secId] || sec.quiz.map(()=>false);
    answeredState[secId][qi] = true;
    if (answeredState[secId].every(Boolean)){
      const cb = document.querySelector('.continue-btn[data-sec="'+secId+'"]');
      if (cb) cb.disabled = false;
    }
  } else {
    btn.classList.add('wrong');
    card.classList.remove('shake'); void card.offsetWidth; card.classList.add('shake');
    feedback.className = 'qfeedback bad';
    feedback.textContent = '__WRONG_FEEDBACK__';
    setTimeout(()=>btn.classList.remove('wrong'), 500);
  }
}

function handleContinue(btn){
  const secId = btn.dataset.sec;
  completed.add(secId);
  saveProgress();
  updateGates();
  const idx = SECTIONS.findIndex(s=>s.id===secId);
  const next = SECTIONS[idx+1];
  if (next) document.getElementById(next.id).scrollIntoView({behavior:'smooth', block:'start'});
  else document.getElementById('page-footer').scrollIntoView({behavior:'smooth'});
}

function updateGates(){
  // A gate is cumulative, not a single lookback: a no-quiz section (a glossary,
  // a closing summary) is always "done" on its own, but it must still carry
  // forward whatever came before it, or it silently reopens the chain for
  // every section after it.
  let chainOk = true;
  SECTIONS.forEach((sec,i)=>{
    const el = document.getElementById(sec.id);
    el.classList.toggle('locked', !chainOk);
    const link = document.getElementById('toc-'+sec.id);
    if (link) link.classList.toggle('done', sectionDone(sec) && completed.has(sec.id));
    chainOk = chainOk && sectionDone(sec);
  });
  const gated = SECTIONS.filter(s=>s.quiz);
  document.getElementById('progress-count').textContent = completed.size + ' / ' + gated.length + ' __PROGRESS_DONE_WORD__';
  document.getElementById('global-progress-fill').style.width = (gated.length ? completed.size/gated.length*100 : 100) + '%';
}

const TIMELINE_NEUTRAL_RGB = [42, 47, 61];   // matches --border
const TIMELINE_ACTIVE_RGB = [232, 185, 59];  // matches --medium
const TIMELINE_MUTED_RGB = [154, 163, 178];  // matches --muted
const TIMELINE_TEXT_RGB = [231, 233, 238];   // matches --text

function timelineMixChannel(a, b, t){ return Math.round(a + (b - a) * t); }

function timelineMixRgb(from, to, t){
  return 'rgb(' + from.map((c, i)=>timelineMixChannel(c, to[i], t)).join(',') + ')';
}

// One shared time axis can carry several parallel lanes (concurrent tasks, an
// await racing another, a fork that later joins). Every node across every lane
// reads the same slider, so lining nodes up vertically is how the markup shows
// two lanes hitting the same instant.
function initTimelines(){
  document.querySelectorAll('.timeline').forEach(tl=>{
    const slider = tl.querySelector('.timeline-slider');
    if (!slider) return;
    const fill = tl.querySelector('.timeline-fill');
    const nowLine = tl.querySelector('.timeline-now-line');
    const nodes = [...tl.querySelectorAll('.timeline-node')];
    const readout = tl.querySelector('.timeline-readout');
    const template = readout ? (readout.dataset.template || '{value}') : null;
    const prevBtn = tl.querySelector('.timeline-prev');
    const nextBtn = tl.querySelector('.timeline-next');
    const min = +slider.min, max = +slider.max;
    // The slider itself moves continuously (step="any"): dragging is smooth, not a
    // snap between states. Prev/Next jump to the nearest node position (pooled
    // across every lane) instead of adding a fixed step, which has no meaning on
    // a continuous track.
    const positions = [...new Set(nodes.map(n=>+n.dataset.pos))].sort((a,b)=>a-b);
    const pctOf = pos => max > min ? (pos - min) / (max - min) * 100 : 0;

    nodes.forEach(node=>{ node.style.left = pctOf(+node.dataset.pos) + '%'; });

    // Each lane's own connecting line spans only from its first node to its
    // last — nothing is happening in that lane before it starts or after it
    // ends, so the line shouldn't run past either end.
    const lanes = [...tl.querySelectorAll('.timeline-lane-row')].map(row=>{
      const laneNodes = [...row.querySelectorAll('.timeline-node')]
        .map(n=>+n.dataset.pos).sort((a,b)=>a-b);
      const track = row.querySelector('.timeline-lane-track');
      if (track){
        const leftPct = laneNodes.length ? pctOf(laneNodes[0]) : 0;
        const rightPct = laneNodes.length ? pctOf(laneNodes[laneNodes.length - 1]) : 0;
        track.style.left = leftPct + '%';
        track.style.width = Math.max(0, rightPct - leftPct) + '%';
      }
      return {track, laneNodes};
    });

    // A link crosses lanes (a fork, a join, a wait on another lane's node),
    // so unlike a lane's own track it can't be positioned with percentages
    // alone — it needs both nodes' actual pixel position once layout settles.
    // Placeholder <div class="timeline-link" data-from="id" data-to="id">
    // elements just declare the pair and are discarded; the rendered line is
    // a plain div this script creates, so no SVG plumbing is needed.
    const grid = tl.querySelector('.timeline-grid');
    const links = [...tl.querySelectorAll('.timeline-link')].map(def=>{
      const from = tl.querySelector('#' + CSS.escape(def.dataset.from || ''));
      const to = tl.querySelector('#' + CSS.escape(def.dataset.to || ''));
      def.remove();
      if (!from || !to || !grid) return null;
      const line = document.createElement('div');
      line.className = 'timeline-link-line';
      grid.appendChild(line);
      return {from, to, line};
    }).filter(Boolean);

    function anchorPoint(node, gridRect){
      const target = node.querySelector('.timeline-dot') || node;
      const r = target.getBoundingClientRect();
      return {x: r.left + r.width / 2 - gridRect.left, y: r.top + r.height / 2 - gridRect.top};
    }

    function positionLinks(){
      if (!links.length || !grid) return;
      const gridRect = grid.getBoundingClientRect();
      links.forEach(({from, to, line})=>{
        const a = anchorPoint(from, gridRect), b = anchorPoint(to, gridRect);
        const length = Math.hypot(b.x - a.x, b.y - a.y);
        const angle = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
        line.style.left = a.x + 'px';
        line.style.top = a.y + 'px';
        line.style.width = length + 'px';
        line.style.transform = 'rotate(' + angle.toFixed(2) + 'deg)';
      });
    }

    // t=0 neutral, t=1 fully reached (stays lit); the immediate next position
    // ahead scales linearly with how close the slider already is, so halfway
    // between two points reads as half-lit. Shared by dots and lane lines so
    // both read the same "how far along" at any instant.
    function intensityAt(value, pos){
      let k = -1;
      positions.forEach((p, i)=>{ if (p <= value) k = i; });
      const idx = positions.indexOf(pos);
      let t;
      if (idx <= k) {
        t = 1;
      } else if (idx === k + 1) {
        const prevPos = k === -1 ? min : positions[k];
        const span = pos - prevPos;
        t = span > 0 ? (value - prevPos) / span : 1;
      } else {
        t = 0;
      }
      return Math.max(0, Math.min(1, t));
    }

    function update(){
      const value = +slider.value;
      const pct = pctOf(value);
      if (fill) fill.style.width = pct + '%';
      if (nowLine) nowLine.style.left = pct + '%';

      nodes.forEach(node=>{
        const t = intensityAt(value, +node.dataset.pos);
        const dot = node.querySelector('.timeline-dot');
        const label = node.querySelector('.timeline-label');
        if (dot){
          const rgb = timelineMixRgb(TIMELINE_NEUTRAL_RGB, TIMELINE_ACTIVE_RGB, t);
          dot.style.borderColor = rgb;
          dot.style.backgroundColor = t > 0.04 ? rgb : '';
          dot.style.boxShadow = t > 0.04
            ? '0 0 ' + (10 * t).toFixed(1) + 'px ' + (2 * t).toFixed(1) + 'px rgba(232,185,59,' + (0.5 * t).toFixed(2) + ')'
            : 'none';
        }
        if (label) label.style.color = timelineMixRgb(TIMELINE_MUTED_RGB, TIMELINE_TEXT_RGB, t);
        node.classList.toggle('reached', t >= 0.999);
      });

      lanes.forEach(({track, laneNodes})=>{
        if (!track || laneNodes.length < 2) return;
        const leftPct = pctOf(laneNodes[0]);
        const span = pctOf(laneNodes[laneNodes.length - 1]) - leftPct;
        const stops = laneNodes.map(pos=>{
          const localPct = span > 0 ? (pctOf(pos) - leftPct) / span * 100 : 0;
          return timelineMixRgb(TIMELINE_NEUTRAL_RGB, TIMELINE_ACTIVE_RGB, intensityAt(value, pos)) + ' ' + localPct.toFixed(1) + '%';
        });
        track.style.background = 'linear-gradient(to right, ' + stops.join(', ') + ')';
      });

      links.forEach(({from, to, line})=>{
        const t1 = intensityAt(value, +from.dataset.pos);
        const t2 = intensityAt(value, +to.dataset.pos);
        const c1 = timelineMixRgb(TIMELINE_NEUTRAL_RGB, TIMELINE_ACTIVE_RGB, t1);
        const c2 = timelineMixRgb(TIMELINE_NEUTRAL_RGB, TIMELINE_ACTIVE_RGB, t2);
        line.style.background = 'linear-gradient(to right, ' + c1 + ', ' + c2 + ')';
      });

      if (readout) readout.textContent = template.replace('{value}', Math.round(value * 10) / 10);
      if (prevBtn) prevBtn.disabled = value <= positions[0];
      if (nextBtn) nextBtn.disabled = value >= positions[positions.length - 1];
    }
    slider.addEventListener('input', update);
    if (prevBtn) prevBtn.addEventListener('click', ()=>{
      const value = +slider.value;
      const target = [...positions].reverse().find(p=>p < value - 1e-9);
      slider.value = target !== undefined ? target : min;
      update();
    });
    if (nextBtn) nextBtn.addEventListener('click', ()=>{
      const value = +slider.value;
      const target = positions.find(p=>p > value + 1e-9);
      slider.value = target !== undefined ? target : max;
      update();
    });
    // Link position depends only on layout (pixels), not on the slider, so it
    // is recomputed on resize but not on every drag tick; color still updates
    // every tick via update() above.
    positionLinks();
    window.addEventListener('resize', positionLinks);
    update();
  });
}

document.addEventListener('click', e=>{
  const opt = e.target.closest('.opt');
  if (opt){ handleOption(opt); return; }
  const cont = e.target.closest('.continue-btn');
  if (cont){ handleContinue(cont); return; }
  const reset = e.target.closest('#reset-progress');
  if (reset){ openResetModal(); return; }
  const unlockAll = e.target.closest('#unlock-all');
  if (unlockAll){ unlockAllSections(); return; }
  const cancelReset = e.target.closest('#reset-cancel');
  if (cancelReset){ closeResetModal(); return; }
  const confirmReset = e.target.closest('#reset-confirm-btn');
  if (confirmReset){ closeResetModal(); resetProgress(); return; }
  if (e.target.id === 'reset-modal-backdrop'){ closeResetModal(); return; }
  const jump = e.target.closest('[data-jump]');
  if (jump){ const t = document.getElementById(jump.dataset.jump); if (t) t.scrollIntoView({behavior:'smooth'}); }
});

hydrateProgress();
updateGates();
initTimelines();
"""


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def favicon_href(emoji: str) -> str:
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">{emoji}</text></svg>'
    return "data:image/svg+xml," + urllib.parse.quote(svg)


TABLE_RE = re.compile(r"<table\b.*?</table>", re.DOTALL | re.IGNORECASE)


def wrap_tables(html: str) -> str:
    """Wrap raw <table> blocks in a scroll container so wide tables scroll
    horizontally on narrow screens instead of overflowing the page."""
    return TABLE_RE.sub(lambda m: f'<div class="table-scroll">{m.group(0)}</div>', html)


def level_class(level: str) -> str:
    l = (level or "").lower()
    if l.startswith("easy") or l.startswith("facil") or l.startswith("fácil"):
        return "easy"
    if l.startswith("hard") or l.startswith("dificil") or l.startswith("difícil"):
        return "hard"
    return "medium"


def shuffle_quiz_options(sections: list) -> None:
    """Shuffle each question's option order in place, once, at build time —
    so option position never signals the answer. Mutates the same dicts used
    for the embedded SECTIONS JSON, so the client-side correct-option index
    matches what's rendered."""
    for s in sections:
        for q in s.get("quiz", []):
            random.shuffle(q["options"])


def render_quiz_html(s: dict, ui: dict) -> str:
    quiz = s.get("quiz")
    if not quiz:
        return ""
    cards = []
    for qi, q in enumerate(quiz):
        options_html = "".join(
            f'<button class="opt" data-oi="{oi}">{chr(65 + oi)}. {opt["text"]}</button>'
            for oi, opt in enumerate(q["options"])
        )
        cards.append(f"""<div class="qcard" data-sec="{s["id"]}" data-qi="{qi}">
  <div class="qcard-head">
    <span class="level-badge {level_class(q.get("level", ""))}">{esc(q.get("level", ""))}</span>
    <span class="qtext">{q["question"]}</span>
  </div>
  <div class="options">{options_html}</div>
  <div class="qfeedback"></div>
</div>""")
    return f"""<div class="quiz-block">
  <div class="quiz-head">\U0001F9E0 {esc(ui["quiz_prompt"])}</div>
  {"".join(cards)}
  <button class="btn continue-btn" data-sec="{s["id"]}" disabled>{esc(ui["continue_btn"])}</button>
</div>"""


def render_review_html(s: dict, ui: dict) -> str:
    r = s.get("review")
    if not r:
        return ""
    verdict = r.get("verdict", "ok")
    items = "".join(
        f'<li class="review-item"><span class="rtag {it.get("tag", "nit")}">{esc(ui.get("tag_" + it.get("tag", "nit"), it.get("tag", "")))}</span>'
        f'<span>{"<span class=rarea>" + esc(it["area"]) + ":</span> " if it.get("area") else ""}{it["text"]}</span></li>'
        for it in r.get("items", [])
    )
    summary = f'<p class="review-summary">{r["summary"]}</p>' if r.get("summary") else ""
    return f"""<div class="review {verdict}">
  <div class="review-head"><span class="review-title">\U0001F50D {esc(ui["review_title"])}</span><span class="verdict {verdict}">{esc(ui["verdict_" + verdict])}</span></div>
  {summary}<ul class="review-items">{items}</ul>
</div>"""


def check_option_balance(spec: dict) -> list:
    """Flag questions where the correct option's length is a tell, and flag a
    quiz set where the correct option's relative length (its rank among that
    question's options) is suspiciously consistent across questions — even if
    it's never the outright longest, always landing in the same relative spot
    (always longest, always shortest, always dead-middle) is its own tell."""
    warnings = []
    rank_fracs = []  # 0.0 = shortest option in its question, 1.0 = longest
    longest_is_correct = 0
    shortest_is_correct = 0
    total_q = 0
    for s in spec.get("sections", []):
        for qi, q in enumerate(s.get("quiz", [])):
            lens = [len(re.sub(r"<[^>]+>", "", o["text"])) for o in q["options"]]   # visible text only
            correct_idx = next(i for i, o in enumerate(q["options"]) if o["correct"])
            correct_len = lens[correct_idx]
            others = [l for i, l in enumerate(lens) if i != correct_idx]
            total_q += 1
            if correct_len == max(lens):
                longest_is_correct += 1
            if correct_len == min(lens):
                shortest_is_correct += 1
            rank = sorted(lens).index(correct_len)
            rank_fracs.append(rank / (len(lens) - 1) if len(lens) > 1 else 0.5)
            avg_other = sum(others) / len(others) if others else 0
            if correct_len > max(others, default=0) and avg_other and correct_len > avg_other * 1.3:
                warnings.append(
                    f"[{s['id']}] Q{qi + 1}: correct option is {correct_len} chars vs "
                    f"avg {avg_other:.0f} for distractors — rebalance so length doesn't signal the answer."
                )
    if total_q:
        if longest_is_correct / total_q > 0.4:
            warnings.append(
                f"Systemic bias: the correct option is the single longest one in "
                f"{longest_is_correct}/{total_q} questions ({longest_is_correct / total_q:.0%}). "
                f"A reader can guess-the-longest and beat the quiz. Shorten correct answers or "
                f"lengthen distractors until this is closer to chance (~1/avg-option-count)."
            )
        if shortest_is_correct / total_q > 0.4:
            warnings.append(
                f"Systemic bias: the correct option is the single shortest one in "
                f"{shortest_is_correct}/{total_q} questions ({shortest_is_correct / total_q:.0%}). "
                f"'Pick the shortest' is just as guessable as 'pick the longest' — lengthen some "
                f"correct answers or shorten some distractors."
            )
        if total_q >= 3:
            mean_rank = sum(rank_fracs) / total_q
            std_rank = (sum((r - mean_rank) ** 2 for r in rank_fracs) / total_q) ** 0.5
            if std_rank < 0.2:
                warnings.append(
                    f"Low variety: the correct option's relative length (shortest/middle/longest "
                    f"within its own question) barely changes across the quiz set (std={std_rank:.2f}). "
                    f"Vary it deliberately question to question — sometimes the correct answer should "
                    f"be the shortest option, sometimes the longest, sometimes in between — so relative "
                    f"length carries no signal at all, in either direction."
                )
    return warnings


# Dense technical material, read to understand and retain, not skimmed.
PROSE_WPM = 150          # fiction is about 250; technical prose with new terms is much slower
CODE_WPM = 70            # code is read token by token, and checked against the prose
SECONDS_PER_QUESTION = 60  # read the question, weigh 4 options, recall the section


_VISUAL_CLASSES = {"diagram", "flow", "timeline"}
_DIV_TAG = re.compile(r"<(/?)div\b([^>]*)>", re.I)


def strip_visual_blocks(html: str) -> str:
    """Remove diagrams, flows, timelines, figures and inline SVG from html.
    They are looked at, not read, so the reading time does not count them."""
    html = re.sub(r"<(svg|figure)\b.*?</\1>", " ", html, flags=re.S | re.I)
    out, pos, depth, skip_from = [], 0, 0, None
    for m in _DIV_TAG.finditer(html):
        closing, attrs = m.group(1), m.group(2)
        if skip_from is None:
            cls = re.search(r'class\s*=\s*"([^"]*)"', attrs)
            if not closing and cls and _VISUAL_CLASSES & set(cls.group(1).split()):
                out.append(html[pos:m.start()])
                skip_from, depth = m.start(), 1
            continue
        depth += -1 if closing else 1
        if depth == 0:
            pos, skip_from = m.end(), None
    if skip_from is None:
        out.append(html[pos:])
    return "".join(out)


def estimate_minutes(sections: list) -> int:
    """Prose / 150 wpm + code / 70 wpm + 60 s per quiz question, rounded up.
    Diagrams (the Diagrams section and any .diagram, .flow, .timeline, svg) are not counted."""
    parts = []
    for s in sections:
        if s["id"] == "diagrams":  # visual reference (paths, boxes), scanned and not read
            continue
        parts += [s.get("lead", ""), strip_visual_blocks(s["html"]), s.get("review", {}).get("summary", "")]
        parts += [i["text"] for i in s.get("review", {}).get("items", [])]
        for q in s.get("quiz", []):
            parts += [q["question"], q["explain"]] + [o["text"] for o in q["options"]]
    text = " ".join(parts)
    text = re.sub(r"<(style|script)\b.*?</\1>", " ", text, flags=re.S)  # diagram blocks carry CSS and JS
    code = " ".join(re.findall(r"<pre\b.*?</pre>", text, flags=re.S))
    prose = re.sub(r"<pre\b.*?</pre>", " ", text, flags=re.S)
    count = lambda h: len(re.sub(r"<[^>]+>", " ", h).split())
    questions = sum(len(s.get("quiz", [])) for s in sections)
    seconds = count(prose) / PROSE_WPM * 60 + count(code) / CODE_WPM * 60 + questions * SECONDS_PER_QUESTION
    return max(1, -(-int(seconds) // 60))


_DIFF_SPAN_NEWLINE = re.compile(r'(<span class="line-(?:add|del)">[^\n]*</span>)\n')


def strip_diff_span_newlines(html: str) -> str:
    """line-add / line-del are display:block, so they already end the line.
    A newline right after the closing </span> shows as an empty line inside <pre>.
    Remove it here so a spec cannot produce those gaps."""
    return _DIFF_SPAN_NEWLINE.sub(r"\1", html)


_PRE_CODE = re.compile(r'<pre(?: data-file="([^"]*)")?><code>(.*?)</code></pre>', re.S)
_LINE_SPAN = re.compile(r'^<span class="line-(add|del)">(.*)</span>$')
# A // comment starts at line start or after whitespace, so "http://" is left alone.
_COMMENT = re.compile(r'(?:^|\s)//\s?(.*)$')


def _split_comment(text: str):
    """Return (code, comment) for one line. Skips a // that sits inside a string literal."""
    for m in re.finditer(r'(?:^|\s)//\s?', text):
        if text[: m.start()].count('"') % 2 == 0:
            return text[: m.start()].rstrip(), text[m.end():].strip()
    return text, ""


def grid_code_blocks(html: str) -> str:
    """Turn each <pre><code> block that has // comments into a two-column grid:
    code on the left, the comment of each line on the right. A comment-only line
    attaches to the next code line. Blocks without comments stay a plain <pre>."""

    def split_lines(raw: str):
        # A line-add / line-del span is one whole line. It ends the line itself, with or without a "\n" after it.
        parts = re.split(r'(<span class="line-(?:add|del)">.*?</span>)', raw, flags=re.S)
        lines = []
        for i, p in enumerate(parts):
            if i % 2 == 1:
                lines.append(p)
                continue
            if i > 0 and p.startswith("\n"):
                p = p[1:]
            seg = p.split("\n")
            if i < len(parts) - 1 and seg and seg[-1] == "":
                seg = seg[:-1]
            lines.extend(seg)
        return lines

    def convert(m):
        lines = split_lines(m.group(2))
        parsed = []
        for ln in lines:
            sm = _LINE_SPAN.match(ln)
            parsed.append((sm.group(1) if sm else "", sm.group(2) if sm else ln, bool(sm)))
        if not any(_split_comment(text)[1] for _, text, _ in parsed):
            return m.group(0)
        rows, pending = [], []
        for kind, text, is_span in parsed:
            code, comment = _split_comment(text)
            if code.strip() == "" and comment.startswith("..."):
                code, comment = "// " + comment, ""  # an elision marker stays a code line
            elif code.strip() == "" and comment:
                pending.append(comment)  # comment-only line: goes to the next code line
                continue
            if code.strip() == "" and not comment and not is_span:
                continue  # blank line
            if comment:
                pending.append(comment)
            rows.append((kind, code, " ".join(pending)))
            pending = []
        if pending and rows:
            kind, code, comment = rows[-1]
            rows[-1] = (kind, code, " ".join(filter(None, [comment] + pending)))
        file_name = m.group(1)
        code_head = f'Code <span class="fn">{file_name}</span>' if file_name else "Code"
        out = [f'<div class="cg" role="table"><div class="h">{code_head}</div><div class="h">What it does</div>']
        for kind, code, comment in rows:
            cls = f" {kind}" if kind else ""
            has = " has" if comment else ""
            out.append(
                f'<div class="r"><div class="c{cls}">{code}</div><div class="n{cls}{has}">{comment}</div></div>'
            )
        out.append("</div>")
        return "".join(out)

    return _PRE_CODE.sub(convert, html)


def render(spec: dict) -> str:
    title = spec["title"]
    subtitle = spec.get("subtitle", "")
    sections = spec["sections"]
    slug = spec.get("slug") or slugify(title)
    favicon = spec.get("favicon", "\U0001F9E0")  # default: brain emoji
    ui = {**DEFAULT_UI, **spec.get("ui", {})}

    for s in sections:
        if "quiz" in s and len(s["quiz"]) != 3:
            raise ValueError(
                f"section '{s['id']}' has {len(s['quiz'])} quiz questions; each gated "
                f"section needs exactly 3 (easy/medium/hard)."
            )

    shuffle_quiz_options(sections)

    toc_items = "\n".join(
        f'  <a href="#{s["id"]}" id="toc-{s["id"]}">{s.get("num", "")} {esc(s["heading"])}</a>'
        for s in sections
    )

    body_sections = []
    for i, s in enumerate(sections):
        quiz_container = (
            f'\n  <div class="quiz-container" data-quiz="{s["id"]}">{render_quiz_html(s, ui)}</div>'
            if "quiz" in s else ""
        )
        lead = f'<p class="lead">{s["lead"]}</p>\n  ' if s.get("lead") else ""
        lock_overlay = ""
        # The gate is cumulative (see updateGates in JS): a no-quiz section (a
        # glossary, a closing summary) carries forward whatever gate came before
        # it instead of resetting the chain, so the overlay must point at the
        # nearest earlier section that actually has a quiz, not just sections[i-1].
        gate = next((sections[j] for j in range(i - 1, -1, -1) if "quiz" in sections[j]), None)
        if gate is not None:
            lock_text = esc(ui["lock_text"]).format(heading=esc(gate["heading"]))
            lock_overlay = f"""
  <div class="lock-overlay">
    <div class="lock-icon">\U0001F512</div>
    <div>{lock_text}</div>
    <button class="btn secondary" data-jump="{gate["id"]}">{esc(ui["lock_link"])}</button>
  </div>"""
        body_sections.append(f"""<section id="{s["id"]}">
  <h2><span class="num">{s.get("num", i + 1)}</span>{esc(s["heading"])}</h2>
  {lead}<div class="sec-body">
  {wrap_tables(grid_code_blocks(strip_diff_span_newlines(s["html"])))}{render_review_html(s, ui)}{quiz_container}
  </div>{lock_overlay}
</section>""")

    sections_json = json.dumps(
        [
            {"id": s["id"], "quiz": s.get("quiz")}
            for s in sections
        ],
        ensure_ascii=False,
    ).replace("</", "<\\/")

    js_engine = (
        JS_ENGINE
        .replace("__WRONG_FEEDBACK__", js_str(ui["wrong_feedback"]))
        .replace("__PROGRESS_DONE_WORD__", js_str(ui["progress_done_word"]))
    )

    return f"""<!DOCTYPE html>
<html lang="{esc(ui["html_lang"])}">
<head>
<meta charset="UTF-8">
<title>{esc(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="{favicon_href(favicon)}">
<style>{CSS}</style>
</head>
<body>

<div id="global-progress-bar"><div id="global-progress-fill"></div></div>
<div id="progress-readout">
  <span id="progress-count">0 {esc(ui["progress_done_word"])}</span>
  <button id="reset-progress" class="reset-btn" title="{esc(ui["reset_label"])}" aria-label="{esc(ui["reset_label"])}">↺</button>
  <button id="unlock-all" class="reset-btn" title="{esc(ui["unlock_all_label"])}" aria-label="{esc(ui["unlock_all_label"])}">🔓</button>
</div>

<div id="reset-modal-backdrop" class="modal-backdrop">
  <div class="modal">
    <p>{esc(ui["reset_confirm"])}</p>
    <div class="modal-actions">
      <button id="reset-cancel" class="btn secondary">{esc(ui["reset_cancel_btn"])}</button>
      <button id="reset-confirm-btn" class="btn">{esc(ui["reset_confirm_btn"])}</button>
    </div>
  </div>
</div>

<header class="hero">
  <h1>{esc(title)}</h1>
  {f'<p>{subtitle}</p>' if subtitle else ''}
  <p class="read-time">⏱ {esc(ui["reading_time"]).format(minutes=estimate_minutes(sections))}</p>
  <nav class="toc">
{toc_items}
  </nav>
</header>

<div class="wrap">

{"".join(body_sections)}

</div>

<footer id="page-footer">{esc(ui["footer_text"])}</footer>

<script>
const SPEC_SLUG = {json.dumps(slug)};
const SECTIONS = {sections_json};
{js_engine}
</script>

</body>
</html>
"""


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path, help="path to the JSON content spec")
    ap.add_argument("-o", "--output", type=Path, default=None, help="output HTML path")
    args = ap.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))

    for w in check_option_balance(spec):
        print(f"WARNING: {w}", file=sys.stderr)

    out_html = render(spec)

    if args.output:
        out_path = args.output
    else:
        date_prefix = datetime.date.today().strftime("%Y-%m-%d")
        slug = spec.get("slug") or slugify(spec["title"])
        out_path = Path.home() / "sDeveloper" / "Docs" / f"{date_prefix}-{slug}.html"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out_html, encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
