// neurobox study gallery: renders window.GALLERY (built by neurobox.gallery.build).
// Every value from a results file is set as text, never as HTML.
(function () {
  "use strict";
  const G = window.GALLERY;
  const $ = (tag, attrs, ...kids) => {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "text") el.textContent = v;
      else if (k === "on") for (const [ev, fn] of Object.entries(v)) el.addEventListener(ev, fn);
      else el.setAttribute(k, v);
    }
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined) el.append(kid);
    return el;
  };
  const content = document.getElementById("content");
  const label = (g) => (G.group_labels && G.group_labels[g]) || g;

  // ---- theme ----
  const theme = localStorage.getItem("neurobox-theme");
  if (theme) document.documentElement.dataset.theme = theme;
  document.getElementById("theme").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("neurobox-theme", next);
  });

  // ---- navigation ----
  const nav = document.getElementById("nav");
  function drawNav(filter) {
    nav.replaceChildren();
    const q = (filter || "").toLowerCase();
    let group = null;
    for (const s of G.sections) {
      const items = s.analyses.map((k) => G.analyses[k]).filter((a) =>
        !q || [a.title, a.id, a.domain, a.description].join(" ").toLowerCase().includes(q));
      if (q && !items.length) continue;
      if (s.group && s.group !== group) { nav.append($("div", { class: "nav-group", text: s.group })); group = s.group; }
      nav.append($("div", { class: "nav-section", text: s.label }));
      if (!items.length) nav.append($("div", { class: "nav-empty", text: "no results yet" }));
      for (const a of items) {
        nav.append($("a", { class: "nav-item", href: "#" + a.key, "data-key": a.key, text: a.title || a.id }));
      }
    }
  }
  document.getElementById("search").addEventListener("input", (e) => drawNav(e.target.value));
  document.getElementById("gallery-title").addEventListener("click", () => { location.hash = ""; });

  // ---- zoom ----
  const zoom = $("div", { id: "zoom", on: { click: () => { zoom.style.display = "none"; } } }, $("img"));
  document.body.append(zoom);
  const zoomTo = (src) => { zoom.firstChild.src = src; zoom.style.display = "flex"; };

  // ---- pieces of an analysis page ----
  function facts(a) {
    const dl = $("dl", { class: "facts" });
    const add = (k, v) => { if (v !== undefined && v !== null && v !== "") dl.append($("dt", { text: k }), $("dd", { text: v })); };
    const d = a.design || {};
    const groups = d.groups ? Object.entries(d.groups)
      .sort((x, y) => (G.group_order.indexOf(x[0]) + 1 || 99) - (G.group_order.indexOf(y[0]) + 1 || 99))
      .map(([g, n]) => `${label(g)} ${n}`).join(", ") : "";
    add("Subjects", d.n !== undefined ? `${d.n}${groups ? " (" + groups + ")" : ""}` : "");
    if (d.sessions) add("Sessions", d.sessions);
    if (d.timepoints) add("Timepoints", d.timepoints.join(", "));
    add("Measures", (a.measures || []).join(", "));
    add("Atlas", a.atlas && a.atlas.name);
    const inf = a.inference || {};
    add("Inference", inf.method);
    if (inf.correction) add("Correction", inf.correction.statement);
    if (inf.families) add("Correction", `${inf.families.length} families: ` +
      [...new Set(inf.families.map((f) => f.method || f.p_kind))].join(", ") + " within each");
    const e = a.effect || {};
    add("Effect", e.measure === null ? e.reason : e.definition);
    add("Run", [a.run.id, a.run.label].filter(Boolean).join(" — "));
    const p = a.provenance || {};
    add("Produced by", (p.generated_by || []).map((g) => `${g.Name} ${g.Version}`).join(", "));
    if (p.status && p.status !== "completed") add("Status", p.status);
    add("Analysis id", a.id);
    return dl;
  }

  function figuresBlock(a) {
    if (!a.figures.length) return null;
    const figs = [...a.figures].sort((x, y) => (y.headline ? 1 : 0) - (x.headline ? 1 : 0));
    return $("div", {}, $("h3", { text: `Figures (${figs.length})` }),
      $("div", { class: "figure-grid" }, figs.map((f, i) =>
        $("div", { class: "figure" + (f.headline ? " headline" : "") },
          $("img", { src: f.path, loading: i < 12 ? "eager" : "lazy", alt: f.caption || "",
            on: { click: () => zoomTo(f.path) } }),
          $("div", { class: "caption", text: [f.caption, f.kind && `(${f.kind})`].filter(Boolean).join(" ") })))));
  }

  function tableBlock(t) {
    const std = (h) => (t.columns[h] || {}).Standard;
    const head = $("tr", {}, t.headers.map((h, i) => $("th", {
      class: std(h) ? "std" : null, title: [(t.columns[h] || {}).Description, std(h) && `standard: ${std(h)}`]
        .filter(Boolean).join("\n"), text: h, on: { click: () => sortBy(i) },
    })));
    const sigCol = t.headers.findIndex((h) => std(h) === "significant");
    const body = $("tbody");
    // rows carry their original index, so link columns (built from that order) stay right after sorting
    let rows = t.rows.map((r, n) => Object.assign(r.slice(), { n })), dir = 1, last = -1;
    const links = t.links || {};
    const cell = (v, i, n) => {
      const col = t.headers[i];
      if (links[col] && links[col][n] && links[col][n].length) {
        return $("td", {}, links[col][n].map((href, k) =>
          $("a", { href, target: "_blank", text: (k ? " " : "") + (href.split("/").pop() || href) })));
      }
      return $("td", { class: i === sigCol && /^(true|TRUE|True)$/.test(v) ? "sig" : null,
        text: /^-?\d+\.\d{5,}(e-?\d+)?$/.test(v) ? Number(v).toPrecision(4) : v });
    };
    const draw = (q) => {
      body.replaceChildren(...rows.filter((r) => !q || r.join(" ").toLowerCase().includes(q)).map((r) =>
        $("tr", {}, r.map((v, i) => cell(v, i, r.n)))));
    };
    function sortBy(i) {
      dir = i === last ? -dir : 1; last = i;
      rows.sort((x, y) => { const a = parseFloat(x[i]), b = parseFloat(y[i]);
        return dir * (isNaN(a) || isNaN(b) ? String(x[i]).localeCompare(String(y[i])) : a - b); });
      draw(filter.value.toLowerCase());
    }
    const filter = $("input", { class: "filter", type: "search", placeholder: "Filter rows",
      on: { input: (e) => draw(e.target.value.toLowerCase()) } });
    draw("");
    return $("div", { class: "card" },
      $("div", { class: "table-head" },
        $("div", {}, $("strong", { text: t.name }), " ",
          $("span", { class: "muted", text: `${t.role || ""} · one row is ${t.rows_are || "?"} · ${t.total_rows} rows` +
            (t.total_rows > t.rows.length ? ` (first ${t.rows.length} shown)` : "") })),
        $("div", {}, filter, " ", $("a", { href: t.path, download: "", text: "CSV" }))),
      t.description ? $("div", { class: "sub", text: t.description }) : null,
      t.threshold ? $("div", { class: "sub", text: `Rows selected by: ${t.threshold.statement}` }) : null,
      $("div", { class: "table-wrap" }, $("table", {}, $("thead", {}, head), body)));
  }

  function analysisPage(a) {
    const tags = [a.modality, a.analysis_type, a.domain, a.task && `task ${a.task}`, a.role]
      .filter(Boolean).map((t) => $("span", { class: "tag" + (t === a.role ? " role-" + t : ""), text: t }));
    const section = G.sections.find((s) => s.key === a.section) || {};
    const parts = [
      $("h2", { text: a.title || a.id }),
      $("div", { class: "sub", text: a.description || "" }),
      $("div", { class: "tags" }, tags),
    ];
    if (section.note) parts.push($("div", { class: "card caveats" }, $("div", { text: section.note })));
    if (a.retired) parts.push($("div", { class: "card caveats", text: `Retired: ${a.retired.reason}` }));
    if (a.caveats && a.caveats.length) {
      parts.push($("div", { class: "card caveats" }, $("strong", { text: "Read with" }),
        $("ul", {}, a.caveats.map((c) => $("li", { text: c })))));
    }
    if (a.decision) {
      const d = a.decision, cal = d.calibration;
      parts.push($("div", { class: "card decision" }, $("strong", { text: "Decision rule " }),
        $("span", { class: "outcome", text: d.outcome.replace(/_/g, " ") }),
        $("div", { class: "sub", text: d.rule }),
        cal ? $("div", { text: `It also holds in ${Math.round(cal.null_rate * 100)}% of datasets with no effect ` +
          `(${cal.method}${cal.datasets ? ", " + cal.datasets : ""}).` }) : null,
        (d.criteria || []).length ? $("ul", {}, d.criteria.map((c) => $("li", {
          text: `${c.passed === true ? "✓" : c.passed === false ? "✗" : "·"} ${c.name}: ${c.description || ""}` }))) : null));
    }
    parts.push($("div", { class: "card" }, facts(a)));
    const figs = figuresBlock(a);
    if (figs) parts.push(figs);
    const tables = [...a.tables].sort((x, y) => (y.headline ? 1 : 0) - (x.headline ? 1 : 0));
    if (tables.length) parts.push($("h3", { text: `Tables (${tables.length})` }), tables.map(tableBlock));
    if (a.maps && a.maps.length) parts.push($("h3", { text: "Maps" }),
      $("div", { class: "muted", text: `${a.maps.length} map(s) in the analysis folder (not copied): ` + a.maps.slice(0, 6).join(", ") + (a.maps.length > 6 ? ", …" : "") }));
    if (a.earlier_runs && a.earlier_runs.length) {
      parts.push($("h3", { text: "Earlier runs" }), $("ul", {}, a.earlier_runs.map((k) => {
        const r = G.runs[k];
        return $("li", { text: `${r.run.id}${r.run.label ? " — " + r.run.label : ""}` });
      })));
    }
    if (a.warnings && a.warnings.length) {
      parts.push($("details", {}, $("summary", { class: "muted", text: `${a.warnings.length} checker warning(s)` }),
        $("ul", {}, a.warnings.map((w) => $("li", { class: "muted", text: w })))));
    }
    return parts;
  }

  function home() {
    const parts = [$("h2", { text: G.title }), G.description ? $("div", { class: "sub", text: G.description }) : null];
    if (G.links.length) parts.push($("div", { class: "tags" }, G.links.map((l) => $("a", { class: "tag", href: l.href, text: l.label }))));
    for (const s of G.sections) {
      parts.push($("div", { class: "card section-card" },
        $("strong", { text: (s.group ? s.group + " · " : "") + s.label }),
        s.analyses.length ? $("ul", {}, s.analyses.map((k) => $("li", {},
          $("a", { href: "#" + k, text: G.analyses[k].title || G.analyses[k].id })))) :
          $("div", { class: "muted", text: "no results yet" })));
    }
    if (G.not_shown.length) {
      parts.push($("div", { class: "card caveats" }, $("strong", { text: "Not shown: these folders do not conform" }),
        $("ul", {}, G.not_shown.map((f) => $("li", { text: `${f.id || f.folder}: ${f.errors.join("; ")}` })))));
    }
    parts.push($("div", { class: "muted", text: `Built ${G.built} from results specification ${G.spec_version}` +
      (G.generator ? ` by ${G.generator}` : "") + "." }));
    return parts;
  }

  function route() {
    const key = decodeURIComponent(location.hash.slice(1));
    const a = G.analyses[key] || G.runs[key];
    content.replaceChildren(...(a ? analysisPage(a) : home()).flat().filter(Boolean));
    for (const el of nav.querySelectorAll(".nav-item")) el.classList.toggle("active", el.dataset.key === key);
    window.scrollTo(0, 0);
  }
  drawNav("");
  window.addEventListener("hashchange", route);
  route();
})();
