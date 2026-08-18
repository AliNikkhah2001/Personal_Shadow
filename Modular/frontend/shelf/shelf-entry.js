import { catalog } from "./catalog.js";
import { ShelfEngine } from "./shelf-engine.js";

const canvas = document.getElementById("shelf-canvas");
const app = document.getElementById("app");
const browseCaption = document.getElementById("browse-caption");
const bookDetails = document.getElementById("book-details");
const bookDetailsInner = document.getElementById("book-details-inner");
const loadingScreen = document.getElementById("loading-screen");
const activeTitle = document.getElementById("active-title");
const activeAuthor = document.getElementById("active-author");
const activeIndexDisplay = document.getElementById("active-index-display");
const inspectBtn = document.getElementById("inspect-btn");
const browsePrevBtn = document.getElementById("browse-prev");
const browseNextBtn = document.getElementById("browse-next");
const shelfTicks = document.getElementById("shelf-ticks");

let engine = null;
let activeIndex = 0;
let selectedIndex = null;
let isFocused = false;

catalog.forEach((_, i) => {
  const tick = document.createElement("button");
  tick.type = "button";
  tick.setAttribute("aria-label", `Browse to ${catalog[i].title}`);
  tick.addEventListener("click", () => engine && engine.browseTo(i));
  shelfTicks.appendChild(tick);
});

function updateTicks() {
  const ticks = shelfTicks.querySelectorAll("button");
  ticks.forEach((t, i) => {
    t.className = i === activeIndex ? "is-active" : "";
    t.setAttribute("aria-current", i === activeIndex ? "true" : "");
  });
}

function updateDetails(book, index) {
  if (!book) {
    bookDetailsInner.innerHTML = "";
    return;
  }
  bookDetailsInner.innerHTML = `
    <button type="button" class="back-button" id="return-btn">
      <span class="arrow-icon arrow-icon--left"><span></span></span>
      <span>Return to shelf</span>
    </button>
    <div class="book-details__position">
      <span>${String(index + 1).padStart(2, "0")}</span>
      <span>${String(catalog.length).padStart(2, "0")}</span>
    </div>
    <div class="book-details__copy">
      <p class="eyebrow">LIBRARY EDITION</p>
      <h2>${book.title}</h2>
      <p class="book-details__author">${book.author}</p>
      <p class="book-details__description">${book.description}</p>
      <blockquote>
        <p>\u201c${book.quote}\u201d</p>
        <cite>${book.quoteBy}</cite>
      </blockquote>
      <dl>
        <div><dt>Format</dt><dd>${book.format}</dd></div>
        <div><dt>Availability</dt><dd>${book.availability}</dd></div>
      </dl>
      <a class="official-link" href="${book.url}" target="_blank" rel="noreferrer">
        <span>View book</span>
        <span aria-hidden="true">\u2197</span>
      </a>
    </div>
    <div class="focus-controls" aria-label="Inspection controls">
      <span>Drag to orbit</span>
      <span>Pinch or scroll to zoom</span>
      <button type="button" id="reset-view-btn">Reset view</button>
    </div>
  `;
  document.getElementById("return-btn").addEventListener("click", () => {
    if (engine) engine.returnToShelf();
  });
  document.getElementById("reset-view-btn").addEventListener("click", () => {
    if (engine) engine.resetFocusView();
  });
}

function setFocused(focused, book, index) {
  isFocused = focused;
  app.className = `press-experience is-ready ${focused ? "is-focused" : "is-browsing"}`;
  browseCaption.setAttribute("aria-hidden", String(focused));
  bookDetails.setAttribute("aria-hidden", String(!focused));
  browsePrevBtn.disabled = focused;
  browseNextBtn.disabled = focused;
  inspectBtn.disabled = focused;
  if (focused) {
    updateDetails(book, index);
  } else {
    updateDetails(null, null);
  }
}

async function init() {
  await document.fonts.ready;

  engine = new ShelfEngine(canvas, catalog, {
    onActiveIndex(idx) {
      activeIndex = idx;
      const book = catalog[idx];
      activeTitle.textContent = book.shortTitle;
      activeAuthor.textContent = book.author;
      activeIndexDisplay.textContent = String(idx + 1).padStart(2, "0");
      updateTicks();
    },
    onMode(mode, idx) {
      if (mode === "inspect" && idx !== null) {
        selectedIndex = idx;
        setFocused(true, catalog[idx], idx);
      } else {
        selectedIndex = null;
        setFocused(false, null, null);
      }
    },
    onStatus(msg) {},
    onReady() {
      loadingScreen.setAttribute("aria-hidden", "true");
      const firstBook = catalog[0];
      activeTitle.textContent = firstBook.shortTitle;
      activeAuthor.textContent = firstBook.author;
      activeIndexDisplay.textContent = "01";
      updateTicks();
    },
  });
}

inspectBtn.addEventListener("click", () => {
  if (engine) engine.focusBook(activeIndex);
});

browsePrevBtn.addEventListener("click", () => {
  if (engine) engine.browseBy(-1);
});

browseNextBtn.addEventListener("click", () => {
  if (engine) engine.browseBy(1);
});

window.addEventListener("message", (e) => {
  if (e.data && e.data.type === "shelf-navigate" && engine) {
    if (typeof e.data.index === "number") engine.browseTo(e.data.index);
    else if (e.data.action === "prev") engine.browseBy(-1);
    else if (e.data.action === "next") engine.browseBy(1);
  }
});

init();
