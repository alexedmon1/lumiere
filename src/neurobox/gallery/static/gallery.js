/* neurobox study gallery: renders window.GALLERY (built by neurobox.gallery.build).

   source-lightbox's front end (layout, navigation, tabs, viewer, grouped tables, search),
   ported onto the results specification. Where lightbox guessed from file names and
   hard-coded lists, this reads declared fields: an analysis's domain, variant, contrasts
   and design; a figure's caption, kind, measure, contrast and facets; a column's Standard
   term. Orders come from the vocabularies (domains), the gallery settings (variants,
   groups) and the tables themselves (facet values in the order rows give them).

   Every value from a results file is escaped before it reaches the page. */
(function () {
  "use strict";

  var M = window.GALLERY;
  var A = M.analyses;                 // the current run of each analysis id, by key
  var KEYS = Object.keys(A);
  var lightbox = null;

  /* ── Display formatting of identifiers (formatting only; nothing is inferred from it) ── */
  var ACRONYMS = {
    psd: "PSD", pac: "PAC", aac: "AAC", ppc: "PPC", roi: "ROI", rois: "ROIs", lmm: "LMM", itc: "ITC",
    ersp: "ERSP", stp: "STP", erp: "ERP", nbs: "NBS", qc: "QC", eeg: "EEG", mri: "MRI", fdr: "FDR",
    fwe: "FWE", se: "SE", df: "df", aec: "AEC", pli: "PLI", wpli: "wPLI", dwpli: "dwPLI", dpli: "dPLI",
    imcoh: "ImCoh", dtf: "DTF", fcd: "FCD", auc: "AUC", tfce: "TFCE", mi: "MI", mde: "MDE", tost: "TOST",
    tbss: "TBSS", vbm: "VBM", tbm: "TBM", dwi: "DWI", mrs: "MRS", asl: "ASL", fa: "FA", md: "MD",
    rd: "RD", ad: "AD", mk: "MK", odi: "ODI", reho: "ReHo", falff: "fALFF", alff: "ALFF", fc: "FC",
    mc: "MC", bh: "BH", id: "id",
  };
  var TYPE_LABELS = {
    sensor: "Sensor-level", roi: "ROI-level", vertex: "Vertex-level", directed: "Directed edges",
    tbss: "TBSS", vbm: "VBM", tbm: "TBM", voxelwise: "Voxelwise", fixel: "Fixel", nbs: "NBS",
    graph: "Graph", connectome: "Connectome", covariance_network: "Covariance network",
    decoding: "Decoding", radiomics: "Radiomics", spectroscopy: "Spectroscopy", other: "Other",
  };
  // Designs without a variant are listed after the variants, sensor-level last (lightbox's order).
  var TYPE_ORDER = ["roi", "vertex", "directed", "tbss", "vbm", "tbm", "voxelwise", "fixel",
                    "connectome", "covariance_network", "nbs", "graph", "decoding", "radiomics",
                    "spectroscopy", "other", "sensor"];
  var KIND_LABELS = {
    brain: "Brain maps", matrix: "Matrices", spectrum: "Spectra", distribution: "Distributions",
    trajectory: "Trajectories", summary: "Summaries", diagnostic: "Diagnostics", other: "Other figures",
  };

  function formatName(slug) {
    return String(slug == null ? "" : slug).replace(/_/g, " ").split(" ").map(function (w) {
      var l = w.toLowerCase();
      if (ACRONYMS[l]) return ACRONYMS[l];
      var hz = l.match(/^(\d+)(hz)$/);
      if (hz) return hz[1] + " Hz";
      return w.charAt(0).toUpperCase() + w.slice(1);
    }).join(" ");
  }
  function esc(v) {
    if (v === null || v === undefined) return "";
    return String(v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function groupLabel(g) { return (M.group_labels && M.group_labels[g]) || String(g).replace(/_/g, " "); }
  function domainLabel(d) {
    if (d === "cross_frequency") return "Cross-frequency";
    return formatName(d);
  }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : (many || one + "s")); }

  /* ── Contrasts, from analysis.json's declared contrasts ── */
  function contrastOf(a, id) {
    return (a.contrasts || []).find(function (c) { return c.id === id; }) || null;
  }
  function contrastLabel(a, id) {
    var c = contrastOf(a, id);
    return (c && c.label) || formatName(id);
  }

  /* ── Where an analysis is listed: group → design → domain ── */
  function sectionOf(a) {
    return M.sections.find(function (s) { return s.key === a.section; }) || {};
  }
  function groupOf(a) { var s = sectionOf(a); return s.group || s.label || "Results"; }
  function domainOf(a) { return a.domain || sectionOf(a).label || a.analysis_type || "other"; }
  function variantSiblings(a) {
    if (!a.variant) return [];
    return KEYS.filter(function (k) {
      var v = A[k].variant;
      return v && v.of === a.variant.of && v.axis === a.variant.axis;
    });
  }
  // A variant is its own study design only beside another variant of the same analysis.
  function designOf(a) {
    if (a.variant && variantSiblings(a).length > 1) {
      var v = a.variant;
      return { key: "v:" + v.axis + ":" + v.value, label: v.label || formatName(v.value),
               axis: v.axis, value: v.value };
    }
    var t = a.analysis_type || "other";
    if (t === "other" && (a.role === "diagnostic" || a.role === "descriptive")) {
      return { key: "r:" + a.role, label: a.role === "diagnostic" ? "Diagnostics" : "Descriptive", type: "other" };
    }
    return { key: "t:" + t, label: TYPE_LABELS[t] || formatName(t), type: t };
  }
  function variantRank(axis, value) {
    var order = (M.variant_order && M.variant_order[axis]) || [];
    var i = order.indexOf(value);
    return i < 0 ? order.length : i;
  }
  function designRank(d) {
    if (d.axis) return [0, variantRank(d.axis, d.value), d.label];
    var i = TYPE_ORDER.indexOf(d.type);
    return [1, i < 0 ? TYPE_ORDER.length : i, d.label];
  }
  function cmpRank(x, y) {
    for (var i = 0; i < x.length; i++) {
      if (x[i] < y[i]) return -1;
      if (x[i] > y[i]) return 1;
    }
    return 0;
  }
  function domainRank(d) {
    var i = (M.domains || []).findIndex(function (x) { return x.name === d; });
    return i < 0 ? 999 : i;
  }

  // [{name, designs: [{key, label, axis, value, domains: [{name, keys}]}]}], built once.
  var TREE = (function () {
    var groups = [], byName = {};
    var keysInOrder = [];
    M.sections.forEach(function (s) { keysInOrder = keysInOrder.concat(s.analyses); });
    KEYS.forEach(function (k) { if (keysInOrder.indexOf(k) < 0) keysInOrder.push(k); });
    keysInOrder.forEach(function (k) {
      var a = A[k];
      if (!a) return;
      var gname = groupOf(a);
      var g = byName[gname];
      if (!g) { g = byName[gname] = { name: gname, designs: [], byKey: {} }; groups.push(g); }
      var d = designOf(a);
      var dd = g.byKey[d.key];
      if (!dd) { dd = g.byKey[d.key] = Object.assign({ domains: [], byName: {} }, d); g.designs.push(dd); }
      var dom = domainOf(a);
      var de = dd.byName[dom];
      if (!de) { de = dd.byName[dom] = { name: dom, keys: [] }; dd.domains.push(de); }
      de.keys.push(k);
    });
    groups.forEach(function (g) {
      g.designs.sort(function (x, y) { return cmpRank(designRank(x), designRank(y)); });
      g.designs.forEach(function (d) {
        d.domains.sort(function (x, y) { return domainRank(x.name) - domainRank(y.name) || (x.name < y.name ? -1 : 1); });
        d.domains.forEach(function (de) {
          de.keys.sort(function (x, y) {
            var ax = A[x], ay = A[y];
            return String(ax.title || ax.id).localeCompare(String(ay.title || ay.id));
          });
        });
      });
    });
    return groups;
  })();

  function domainRoute(gi, dkey, domain) {
    return "/d/" + gi + "/" + encodeURIComponent(dkey) + "/" + encodeURIComponent(domain);
  }
  function analysisRoute(key) { return "/a/" + encodeURIComponent(key); }
  function placeOf(key) {               // [group index, design, domain entry] of an analysis
    for (var gi = 0; gi < TREE.length; gi++) {
      for (var d of TREE[gi].designs) {
        for (var de of d.domains) if (de.keys.indexOf(key) >= 0) return [gi, d, de];
      }
    }
    return null;
  }

  /* ── Init ── */
  document.addEventListener("DOMContentLoaded", function () {
    document.title = M.title || "Gallery";
    buildSidebar();
    initThemeToggle();
    initSearch();
    initKeyboard();
    window.addEventListener("hashchange", route);
    route();
  });

  /* ── Router ── */
  function route() {
    var hash = location.hash.slice(1) || "/";
    var parts = hash.split("/").filter(Boolean).map(decodeURIComponent);
    highlightNav(hash);
    if (parts[0] === "search") renderSearch(parts.slice(1).join("/"));
    else if (parts[0] === "d") renderDomain(parseInt(parts[1], 10), parts[2] || "", parts[3] || "");
    else if (parts[0] === "a") renderAnalysis(parts[1]);
    else if (parts.length === 1 && (A[parts[0]] || M.runs[parts[0]])) renderAnalysis(parts[0]);  // old links
    else renderOverview();
    window.scrollTo(0, 0);
  }

  /* ── Sidebar ── */
  function navItem(route, label, extra) {
    return '<a class="nav-item" href="#' + esc(route) + '" data-route="' + esc(route) + '">' + esc(label) +
      (extra || "") + "</a>";
  }
  function buildSidebar() {
    var html = navItem("/", "Overview");
    TREE.forEach(function (g, gi) {
      html += '<div class="nav-divider"></div>';
      html += '<div class="nav-section-title">' + esc(g.name) + "</div>";
      g.designs.forEach(function (d) {
        if (g.designs.length > 1 || d.axis) html += '<div class="nav-study-design">' + esc(d.label) + "</div>";
        d.domains.forEach(function (de) {
          var n = de.keys.length;
          html += navItem(domainRoute(gi, d.key, de.name), domainLabel(de.name),
            n > 1 ? ' <span class="tab-count">' + n + "</span>" : "");
        });
      });
    });
    if (M.links && M.links.length) {
      html += '<div class="nav-divider"></div><div class="nav-section-title">Links</div>';
      M.links.forEach(function (l) {
        html += '<a class="nav-item" href="' + esc(l.href) + '">' + esc(l.label) + "</a>";
      });
    }
    document.getElementById("sidebar-nav").innerHTML = html;
  }
  function highlightNav(hash) {
    var h = hash.replace(/^#/, "") || "/";
    document.querySelectorAll(".nav-item").forEach(function (el) {
      el.classList.toggle("active", el.getAttribute("data-route") === h);
    });
  }

  /* ── Overview ── */
  function statCard(value, label) {
    return '<div class="stat-card"><div class="stat-value">' + esc(value) + '</div><div class="stat-label">' +
      esc(label) + "</div></div>";
  }
  function renderOverview() {
    setBreadcrumb(["Overview"]);
    clearSelector();
    var nFig = 0, nTab = 0, designs = 0;
    KEYS.forEach(function (k) { nFig += A[k].figures.length; nTab += A[k].tables.length; });
    TREE.forEach(function (g) { designs += g.designs.length; });
    var html = '<h2 class="section-header">' + esc(M.title) + "</h2>";
    if (M.description) html += '<p class="page-lead">' + esc(M.description) + "</p>";
    html += '<div class="overview-grid">' + statCard(KEYS.length, KEYS.length === 1 ? "Analysis" : "Analyses") +
      statCard(nFig, "Figures") + statCard(nTab, "Tables") + statCard(designs, designs === 1 ? "Design" : "Designs") +
      "</div>";
    TREE.forEach(function (g, gi) {
      html += '<h2 class="section-header">' + esc(g.name) + "</h2>";
      g.designs.forEach(function (d) {
        html += '<h3 style="margin:12px 0 6px">' + esc(d.label) + "</h3><ul>";
        d.domains.forEach(function (de) {
          var nf = 0, nt = 0;
          de.keys.forEach(function (k) { nf += A[k].figures.length; nt += A[k].tables.length; });
          html += '<li><a href="#' + esc(domainRoute(gi, d.key, de.name)) + '">' + esc(domainLabel(de.name)) +
            "</a> — " + plural(de.keys.length, "analysis", "analyses") + ", " + plural(nf, "figure") + ", " +
            plural(nt, "table") + "</li>";
        });
        html += "</ul>";
      });
    });
    if (M.not_shown && M.not_shown.length) {
      html += '<div class="analysis-warn"><b>Not shown: ' + plural(M.not_shown.length, "folder") +
        " that do not conform</b><ul>";
      M.not_shown.forEach(function (f) {
        html += "<li>" + esc(f.id || f.folder) + ": " + esc((f.errors || []).join("; ")) + "</li>";
      });
      html += "</ul></div>";
    }
    html += '<p class="table-note">Built ' + esc(M.built) + " from results specification " + esc(M.spec_version) +
      (M.generator ? " by " + esc(M.generator) : "") + ".</p>";
    setContent(html);
  }

  /* ── Domain page: one page per group × design × domain, a pill per analysis ── */
  function renderDomain(gi, dkey, domain) {
    var g = TREE[gi];
    if (!g) return notFound("Group not found");
    if (dkey.indexOf("compare:") === 0) return renderCompare(gi, dkey.slice(8), domain);
    var d = g.byKey[dkey];
    var de = d && d.byName[domain];
    if (!de) return notFound("Nothing here");
    setBreadcrumb([g.name, d.label, domainLabel(domain)]);
    variantSelector(gi, d, domain);
    var html = '<h2 class="section-header">' + esc(domainLabel(domain)) +
      ' <span class="domain-sub">' + esc(d.label) + "</span></h2>";
    var build = function (k, prefix) { return analysisInner(A[k], prefix, de.keys.length > 1); };
    html += pillPage(de.keys);
    setContent(html);
    bindPills(de.keys, build);
  }

  // The other variants (designs on the same axis) in this group with this domain, as a selector.
  function variantSelector(gi, d, domain) {
    var g = TREE[gi];
    var axis = d.axis;
    var options = axis ? g.designs.filter(function (x) { return x.axis === axis && x.byName[domain]; }) : [];
    if (options.length < 2) return clearSelector();
    var html = "<label>" + esc(formatName(axis)) + ": <select id='source-select'>";
    options.forEach(function (x) {
      html += '<option value="' + esc(x.key) + '"' + (x.key === d.key ? " selected" : "") + ">" + esc(x.label) + "</option>";
    });
    html += '<option value="compare:' + esc(axis) + '"' + (d.key === "compare:" + axis ? " selected" : "") +
      ">Compare all</option></select></label>";
    document.getElementById("source-selector").innerHTML = html;
    document.getElementById("source-select").addEventListener("change", function (e) {
      location.hash = "#" + domainRoute(gi, e.target.value, domain);
    });
  }

  // Compare all: every analysis of this domain with variants on `axis`, one pill per analysis,
  // its variants' figures side by side.
  function renderCompare(gi, axis, domain) {
    var g = TREE[gi];
    var designs = g.designs.filter(function (x) { return x.axis === axis && x.byName[domain]; });
    if (!designs.length) return notFound("Nothing to compare");
    var byOf = {}, order = [];
    designs.forEach(function (x) {
      x.byName[domain].keys.forEach(function (k) {
        var of = A[k].variant.of;
        if (!byOf[of]) { byOf[of] = []; order.push(of); }
        byOf[of].push(k);
      });
    });
    setBreadcrumb([g.name, "Compare every " + formatName(axis), domainLabel(domain)]);
    variantSelector(gi, { axis: axis, key: "compare:" + axis }, domain);
    var html = '<h2 class="section-header">' + esc(domainLabel(domain)) +
      ' <span class="domain-sub">every ' + esc(formatName(axis)) + "</span></h2>";
    var build = function (of) {
      var keys = byOf[of].slice().sort(function (x, y) {
        return variantRank(axis, A[x].variant.value) - variantRank(axis, A[y].variant.value);
      });
      var cols = keys.map(function (k) {
        var a = A[k];
        return '<div class="comparison-column"><h3><a href="#' + esc(analysisRoute(k)) + '">' +
          esc(a.variant.label || formatName(a.variant.value)) + "</a></h3>" +
          figureRows(orderedFigures(a), "cmp-" + k) + "</div>";
      });
      return { html: '<div class="comparison-grid">' + cols.join("") + "</div>", tables: [], analysis: null };
    };
    var titles = {};
    order.forEach(function (of) { var a = A[byOf[of][0]]; titles[of] = a.title || of; });
    html += pillPage(order, function (of) { return titles[of]; });
    setContent(html);
    bindPills(order, build);
  }

  function pillPage(items, labelOf) {
    labelOf = labelOf || function (k) { return A[k].title || A[k].id; };
    var html = "";
    if (items.length > 1) {
      html += '<div class="pill-bar" role="tablist">';
      items.forEach(function (k, i) {
        html += '<button class="pill' + (i === 0 ? " active" : "") + '" data-pill="' + i + '">' + esc(labelOf(k)) + "</button>";
      });
      html += "</div>";
    }
    items.forEach(function (k, i) {
      html += '<div class="pill-panel' + (i === 0 ? " active" : "") + '" data-pillpanel="' + i + '"></div>';
    });
    return html;
  }
  function bindPills(items, build) {
    var done = {};
    function fill(i) {
      if (done[i]) return;
      done[i] = true;
      var cont = document.querySelector('[data-pillpanel="' + i + '"]');
      var inner = build(items[i], "p" + i);
      cont.innerHTML = inner.html;
      bindInner(cont, inner);
    }
    fill(0);
    document.querySelectorAll(".pill").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var i = parseInt(btn.getAttribute("data-pill"), 10);
        document.querySelectorAll(".pill").forEach(function (b) { b.classList.toggle("active", b === btn); });
        document.querySelectorAll(".pill-panel").forEach(function (p) {
          p.classList.toggle("active", p.getAttribute("data-pillpanel") === String(i));
        });
        fill(i);
      });
    });
  }

  /* ── Analysis page (deep links, search results, earlier runs) ── */
  function renderAnalysis(key) {
    var a = A[key] || M.runs[key];
    if (!a) return notFound("Analysis not found");
    var current = A[key] ? key : KEYS.find(function (k) { return A[k].id === a.id; });
    var place = current && placeOf(current);
    if (place) setBreadcrumb([TREE[place[0]].name, place[1].label, domainLabel(place[2].name), a.title || a.id]);
    else setBreadcrumb([a.title || a.id]);
    clearSelector();
    var inner = analysisInner(a, "a", false);
    var html = '<h2 class="section-header">' + esc(a.title || a.id) + "</h2>";
    if (!A[key]) html += '<div class="analysis-warn">An earlier run of this analysis (' + esc(a.run.id) +
      "), kept for reference; the current run is listed in the navigation.</div>";
    setContent(html + inner.html);
    bindInner(document.getElementById("page"), inner);
  }

  /* ── One analysis: about, cautions, what produced it, then Summary / Figures / Tables ── */
  function analysisInner(a, prefix, subHeader) {
    var html = "";
    if (subHeader) {
      html += '<h3 class="analysis-sub-header"><a href="#' + esc(analysisRoute(a.key)) + '">' +
        esc(a.title || a.id) + "</a></h3>";
    }
    if (a.description) {
      html += '<div class="analysis-about"><span class="about-label">About this analysis</span> ' +
        esc(a.description) + "</div>";
    }
    var tags = [a.modality, a.analysis_type, a.task && "task " + a.task, a.role].filter(Boolean);
    html += '<div class="tags">' + tags.map(function (t) {
      return '<span class="tag' + (t === a.role ? " role-" + esc(t) : "") + '">' + esc(t) + "</span>";
    }).join("") + "</div>";
    var section = sectionOf(a);
    if (section.note) html += '<div class="analysis-warn">' + esc(section.note) + "</div>";
    if (a.retired) html += '<div class="analysis-warn"><b>Retired</b> — ' + esc(a.retired.reason) +
      (a.retired.superseded_by ? " (superseded by " + esc(a.retired.superseded_by) + ")" : "") + "</div>";
    if (a.caveats && a.caveats.length) {
      html += '<div class="analysis-warn"><b>Read with</b><ul>' +
        a.caveats.map(function (c) { return "<li>" + esc(c) + "</li>"; }).join("") + "</ul></div>";
    }
    html += provenanceHtml(a) + measuresHtml(a);

    var tabs = [];
    var summary = summaryHtml(a);
    if (summary) tabs.push({ id: "summary", label: "Summary", count: null, html: summary });
    var figs = figuresPanel(a, prefix);
    if (figs) tabs.push({ id: "figures", label: "Figures", count: a.figures.length, html: figs });
    var tables = orderedTables(a);
    if (tables.length) tabs.push({ id: "tables", label: "Tables", count: tables.length, html: tablesPanel(tables, prefix) });
    if (!tabs.length) {
      html += '<div class="empty-state"><p>No figures, tables or summary for this analysis.</p></div>';
    } else {
      html += '<div class="tab-bar" role="tablist">';
      tabs.forEach(function (t, i) {
        html += '<button class="tab-btn' + (i === 0 ? " active" : "") + '" data-tab="' + t.id + '" role="tab">' +
          esc(t.label) + (t.count != null ? ' <span class="tab-count">' + t.count + "</span>" : "") + "</button>";
      });
      html += "</div>";
      tabs.forEach(function (t, i) {
        html += '<div class="tab-panel' + (i === 0 ? " active" : "") + '" data-panel="' + t.id + '">' + t.html + "</div>";
      });
    }
    return { html: html, tables: tables, analysis: a };
  }

  function bindInner(root, inner) {
    initLightbox();
    bindTabs(root);
    if (inner.analysis) bindTableToggles(root, inner.tables, inner.analysis);
    bindMetricTabs(root);
    bindFigureGroups(root);
  }

  // "What produced this": the design, inference, run and producer, collapsed.
  function provenanceHtml(a) {
    var bits = [];
    var add = function (k, v) { if (v !== undefined && v !== null && v !== "") bits.push([k, v]); };
    var d = a.design || {};
    var order = M.group_order || [];
    var groups = d.groups ? Object.keys(d.groups).sort(function (x, y) {
      return ((order.indexOf(x) + 1) || 99) - ((order.indexOf(y) + 1) || 99);
    }).map(function (gname) { return groupLabel(gname) + " " + d.groups[gname]; }).join(", ") : "";
    add("subjects", d.n !== undefined ? d.n + (groups ? " (" + groups + ")" : "") : "");
    if (d.sessions) add("sessions", d.sessions);
    if (d.timepoints) add("timepoints", d.timepoints.join(", "));
    if (a.variant) add(a.variant.axis, a.variant.label || a.variant.value);
    add("atlas", a.atlas && a.atlas.name + (a.atlas.version ? " " + a.atlas.version : ""));
    var inf = a.inference || {};
    add("inference", inf.method);
    if (inf.correction) add("correction", inf.correction.statement);
    if (inf.families) add("correction", plural(inf.families.length, "family", "families") + ": " +
      Array.from(new Set(inf.families.map(function (f) { return f.method || f.p_kind; }))).join(", ") + " within each");
    var e = a.effect || {};
    add("effect", e.measure === null ? e.reason : e.definition);
    add("run", [a.run && a.run.id, a.run && a.run.label].filter(Boolean).join(" — "));
    var p = a.provenance || {};
    add("produced by", (p.generated_by || []).map(function (gb) { return gb.Name + " " + gb.Version; }).join(", "));
    if (p.status && p.status !== "completed") add("status", p.status);
    add("analysis id", a.id);
    var lead = (p.generated_by || []).slice(0, 1).map(function (gb) { return gb.Name + " " + gb.Version; })
      .concat([a.run && a.run.id]).filter(Boolean).join(" · ");
    var html = '<details class="analysis-prov"><summary>What produced this' + (lead ? " — " + esc(lead) : "") +
      "</summary><dl>";
    bits.forEach(function (b) { html += "<dt>" + esc(b[0]) + "</dt><dd>" + esc(String(b[1])) + "</dd>"; });
    html += "</dl>";
    if (a.earlier_runs && a.earlier_runs.length) {
      html += '<div class="prov-extra"><b>Earlier runs</b><ul>' + a.earlier_runs.map(function (k) {
        var r = M.runs[k];
        return '<li><a href="#' + esc(analysisRoute(k)) + '">' + esc(r.run.id) + "</a>" +
          (r.run.label ? " — " + esc(r.run.label) : "") + "</li>";
      }).join("") + "</ul></div>";
    }
    if (a.warnings && a.warnings.length) {
      html += '<div class="prov-extra"><b>' + plural(a.warnings.length, "checker warning") + "</b><ul>" +
        a.warnings.map(function (w) { return "<li>" + esc(w) + "</li>"; }).join("") + "</ul></div>";
    }
    return html + "</details>";
  }

  // What each measure is, from the measure vocabulary (lightbox's metric glossary, for any modality).
  function measuresHtml(a) {
    var known = (a.measures || []).filter(function (m) { return M.measures && M.measures[m]; });
    if (!known.length) return "";
    return '<details class="metric-glossary"><summary class="metric-glossary-summary">' +
      (known.length === 1 ? "The measure" : "The " + known.length + " measures") +
      '</summary><dl class="metric-glossary-list">' + known.map(function (m) {
        return "<dt>" + esc(m) + "</dt><dd>" + esc(M.measures[m]) + "</dd>";
      }).join("") + "</dl></details>";
  }

  /* ── Summary: the decision, and the declared contrasts by tier ── */
  function summaryHtml(a) {
    var html = "";
    if (a.decision) {
      var d = a.decision, cal = d.calibration;
      html += '<div class="decision"><b>Decision rule</b> <span class="outcome outcome-' + esc(d.outcome) + '">' +
        esc(String(d.outcome).replace(/_/g, " ")) + "</span><div>" + esc(d.rule) + "</div>";
      if (cal) html += "<div>It also holds in " + esc(Math.round(cal.null_rate * 100)) +
        "% of datasets with no effect (" + esc(cal.method) + (cal.datasets ? ", " + esc(cal.datasets) : "") + ").</div>";
      if (d.criteria && d.criteria.length) {
        html += "<ul>" + d.criteria.map(function (c) {
          return "<li>" + (c.passed === true ? "✓" : c.passed === false ? "✗" : "·") + " " + esc(c.name) +
            (c.description ? ": " + esc(c.description) : "") + "</li>";
        }).join("") + "</ul>";
      }
      html += "</div>";
    }
    var cs = a.contrasts || [];
    if (cs.length) {
      var tiers = [], byTier = {};
      cs.forEach(function (c) {
        var t = c.tier || "";
        if (!byTier[t]) { byTier[t] = []; tiers.push(t); }
        byTier[t].push(c);
      });
      html += '<div class="sig-summary"><div class="sig-top">' + plural(cs.length, "contrast") + " tested</div>";
      tiers.forEach(function (t) {
        if (t) html += '<div class="sig-group">' + esc(formatName(t)) + "</div>";
        html += '<ul class="sig-list">';
        byTier[t].forEach(function (c) {
          var pair = c.group_a && c.group_b ? groupLabel(c.group_a) + " vs " + groupLabel(c.group_b) : "";
          html += '<li class="sig-item"><span class="sig-contrast">' + esc(c.label || formatName(c.id)) + "</span>" +
            (c.role ? ' <span class="sig-role sig-role-' + esc(c.role) + '">' + esc(c.role) + "</span>" : "") +
            (c.gate_on && c.gate_on.length ? ' <span class="sig-role sig-gate" title="Only read if the gating contrast holds">gated on ' +
              esc(c.gate_on.map(function (gid) { return contrastLabel(a, gid); }).join(", ")) + "</span>" : "") +
            (c.kind && c.kind !== "contrast" ? ' <span class="sig-facet">' + esc(c.kind) + "</span>" : "") +
            (pair ? ' <span class="sig-pairs">' + esc(pair) + "</span>" : "") + "</li>";
        });
        html += "</ul>";
      });
      html += "</div>";
    }
    return html;
  }

  /* ── Figures: grouped by what they declare ── */
  // The order each facet's values appear in the analysis's tables (rows are written in the
  // study's order: bands low to high, regions as configured).
  var facetCache = {};
  function facetOrders(a) {
    if (facetCache[a.key]) return facetCache[a.key];
    var out = {};
    a.tables.forEach(function (t) {
      t.headers.forEach(function (h, i) {
        var c = t.columns[h] || {};
        if (c.Standard !== "facet") return;
        var name = c.FacetName || "facet";
        var seen = out[name] = out[name] || [];
        t.rows.forEach(function (r) { if (r[i] !== "" && seen.indexOf(r[i]) < 0) seen.push(r[i]); });
      });
    });
    facetCache[a.key] = out;
    return out;
  }
  function figFacet(f, name) {
    if (f.facets && f.facets[name] !== undefined) return f.facets[name];
    if (name === "facet" && f.facet !== undefined) return f.facet;
    return null;
  }
  function axisValue(f, axis) {
    if (axis === "measure" || axis === "contrast" || axis === "kind") return f[axis] || null;
    return figFacet(f, axis.slice(6));
  }
  function axisLabel(a, axis, v) {
    if (axis === "contrast") return contrastLabel(a, v);
    if (axis === "kind") return KIND_LABELS[v] || formatName(v);
    return formatName(v);
  }
  function axisRank(a, axis) {
    var list = axis === "measure" ? (a.measures || []) :
      axis === "contrast" ? (a.contrasts || []).map(function (c) { return c.id; }) :
      axis === "kind" ? Object.keys(KIND_LABELS) : (facetOrders(a)[axis.slice(6)] || []);
    return function (v) { var i = list.indexOf(v); return i < 0 ? list.length : i; };
  }
  function figureAxes(figs) {
    var axes = ["kind", "contrast", "measure"];
    figs.forEach(function (f) {
      Object.keys(f.facets || {}).forEach(function (n) { if (axes.indexOf("facet:" + n) < 0) axes.push("facet:" + n); });
      if (f.facet !== undefined && axes.indexOf("facet:facet") < 0) axes.push("facet:facet");
    });
    return axes;
  }
  function partition(a, figs, axis) {
    var map = {}, order = [];
    figs.forEach(function (f) {
      var v = axisValue(f, axis);
      v = v === null || v === undefined || v === "" ? "__other__" : String(v);
      if (!map[v]) { map[v] = []; order.push(v); }
      map[v].push(f);
    });
    var rank = axisRank(a, axis);
    order.sort(function (x, y) {
      if (x === "__other__") return 1;
      if (y === "__other__") return -1;
      return rank(x) - rank(y) || x.localeCompare(y);
    });
    return { map: map, order: order, matched: figs.length - (map.__other__ ? map.__other__.length : 0),
             distinct: order.filter(function (v) { return v !== "__other__"; }).length };
  }
  // Within a group, figures in the order of their facets' values, then by caption.
  function sortFigures(a, figs) {
    var orders = facetOrders(a), names = Object.keys(orders);
    return figs.slice().sort(function (x, y) {
      for (var n of names) {
        var o = orders[n], ix = o.indexOf(String(figFacet(x, n))), iy = o.indexOf(String(figFacet(y, n)));
        if (ix < 0) ix = o.length;
        if (iy < 0) iy = o.length;
        if (ix !== iy) return ix - iy;
      }
      return String(x.caption || x.path).localeCompare(String(y.caption || y.path));
    });
  }
  function orderedFigures(a) {
    var figs = sortFigures(a, a.figures);
    return figs.filter(function (f) { return f.headline; }).concat(figs.filter(function (f) { return !f.headline; }));
  }

  function figuresPanel(a, prefix) {
    var figs = a.figures;
    if (!figs.length) return "";
    var gallery = "g-" + prefix + "-" + a.key;
    var head = figs.filter(function (f) { return f.headline; });
    var rest = figs.filter(function (f) { return !f.headline; });
    var html = head.length ? figureRows(head, gallery, true) : "";
    // matrices of a contrast in two named facets (lightbox's circos layout): tabs by the first
    // facet, a row of small figures per value of the second
    var grid = rest.filter(function (f) {
      return f.kind === "matrix" && f.contrast && f.facets && Object.keys(f.facets).length >= 2;
    });
    if (grid.length >= 4) {
      rest = rest.filter(function (f) { return grid.indexOf(f) < 0; });
      html += matrixTabs(a, grid, gallery);
    }
    if (rest.length > 8) {
      var nested = nestedGroups(a, rest);
      if (nested) return html + renderGroups(a, nested, gallery, true);
      var single = singleGroups(a, rest);
      if (single) return html + renderGroups(a, single, gallery, false);
    }
    return html + (rest.length ? figureRows(sortFigures(a, rest), gallery, false, true) : "");
  }
  // Measure first, then figure kind (lightbox's measure-first layout), when both split the set.
  function nestedGroups(a, figs) {
    var m = partition(a, figs, "measure");
    if (m.distinct < 2 || m.matched < 0.5 * figs.length) return null;
    var k = partition(a, figs, "kind");
    if (k.distinct < 2) return null;
    return m.order.map(function (v) {
      var sub = partition(a, m.map[v], "kind");
      return { label: v === "__other__" ? "Other" : axisLabel(a, "measure", v), count: m.map[v].length,
               subs: sub.order.map(function (kv) {
                 return { label: kv === "__other__" ? "Other" : axisLabel(a, "kind", kv), figs: sub.map[kv] };
               }) };
    });
  }
  // The first declared axis that splits the set usefully: 2 to 15 groups covering 60% of it.
  function singleGroups(a, figs) {
    var axes = figureAxes(figs);
    for (var axis of axes) {
      var p = partition(a, figs, axis);
      if (p.distinct < 2 || p.distinct > 15 || p.matched < 0.6 * figs.length) continue;
      if (axis === "kind") {
        var share = Math.max.apply(null, p.order.map(function (v) { return p.map[v].length; })) / figs.length;
        if (share > 0.7) continue;
      }
      return p.order.map(function (v) {
        return { label: v === "__other__" ? "Other" : axisLabel(a, axis, v), count: p.map[v].length, figs: p.map[v] };
      });
    }
    return null;
  }
  function renderGroups(a, groups, gallery, nested) {
    var html = '<div class="figure-groups"><div class="fig-group-controls">' +
      '<button type="button" class="fig-toggle-all" data-open="1">Expand all</button>' +
      '<button type="button" class="fig-toggle-all" data-open="0">Collapse all</button></div>';
    groups.forEach(function (g) {
      html += '<details class="fig-group"><summary class="fig-group-summary">' + esc(g.label) +
        ' <span class="fig-group-count">' + g.count + "</span></summary>";
      if (nested) {
        g.subs.forEach(function (s) {
          html += '<div class="fig-subgroup-title">' + esc(s.label) + ' <span class="fig-group-count">' +
            s.figs.length + "</span></div>" + figureRows(sortFigures(a, s.figs), gallery);
        });
      } else {
        html += figureRows(sortFigures(a, g.figs), gallery);
      }
      html += "</details>";
    });
    return html + "</div>";
  }
  // Figures open on the page (a headline, an ungrouped set) load at once; the rest when scrolled to.
  function figureRows(figs, gallery, headline, eager) {
    if (!figs.length) return '<div class="empty-state"><p>No figures</p></div>';
    return '<div class="figure-rows">' + figs.map(function (f, i) {
      var load = headline || (eager && i < 8) ? "eager" : "lazy";
      var cap = f.caption || f.path.split("/").pop();
      return '<figure class="figure-row' + (headline ? " headline" : "") + '"><figcaption>' + esc(cap) +
        (f.kind ? ' <span class="fig-kind">' + esc(f.kind) + "</span>" : "") + "</figcaption>" +
        '<a href="' + esc(f.path) + '" class="glightbox" data-gallery="' + esc(gallery) + '" data-title="' + esc(cap) + '">' +
        '<img src="' + esc(f.path) + '" alt="' + esc(cap) + '" loading="' + load + '"></a></figure>';
    }).join("") + "</div>";
  }
  function matrixTabs(a, figs, gallery) {
    var names = Object.keys(figs[0].facets);
    var tabAxis = "facet:" + names[0], rowAxis = "facet:" + names[1];
    var tabs = partition(a, figs, tabAxis);
    var html = '<div class="matrix-figures"><div class="metric-tabs" role="tablist">';
    tabs.order.forEach(function (v, i) {
      html += '<button class="metric-tab' + (i === 0 ? " active" : "") + '" data-mtab="' + esc(v) + '">' +
        esc(axisLabel(a, tabAxis, v)) + "</button>";
    });
    html += "</div>";
    tabs.order.forEach(function (v, i) {
      html += '<div class="metric-panel' + (i === 0 ? " active" : "") + '" data-mpanel="' + esc(v) + '">';
      var rows = partition(a, tabs.map[v], rowAxis);
      rows.order.forEach(function (rv) {
        html += '<div class="band-block"><h4 class="band-title">' + esc(axisLabel(a, rowAxis, rv)) + '</h4><div class="band-figs">';
        rows.map[rv].forEach(function (f) {
          html += '<figure class="circos-thumb"><a class="glightbox" href="' + esc(f.path) + '" data-gallery="' +
            esc(gallery) + '"><img src="' + esc(f.path) + '" loading="lazy" alt="' + esc(f.caption) + '"></a>' +
            "<figcaption>" + esc(contrastLabel(a, f.contrast)) + "</figcaption></figure>";
        });
        html += "</div></div>";
      });
      html += "</div>";
    });
    return html + "</div>";
  }

  /* ── Tables: collapsed, grouped by their Standard terms ── */
  function orderedTables(a) {
    return a.tables.slice().sort(function (x, y) { return (y.headline ? 1 : 0) - (x.headline ? 1 : 0); });
  }
  function tablesPanel(tables, prefix) {
    var html = '<div class="tables-section">';
    tables.forEach(function (t, i) {
      var id = prefix + "-tbl-" + i;
      html += '<button class="table-toggle" data-table-idx="' + i + '" data-table-id="' + esc(id) + '">' +
        '<span class="arrow">&#9654;</span> ' + esc(t.name) + ' <span class="table-meta">' +
        esc([t.role, t.rows_are && "one row is " + t.rows_are, plural(t.total_rows, "row")].filter(Boolean).join(" · ")) +
        "</span>" + (t.headline ? ' <span class="sig-role">headline</span>' : "") + "</button>";
      if (t.description) html += '<div class="table-desc">' + esc(t.description) + "</div>";
      html += '<div id="' + esc(id) + '" class="table-container" style="display:none"></div>';
    });
    return html + "</div>";
  }
  function bindTableToggles(root, tables, a) {
    root.querySelectorAll(".table-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var container = document.getElementById(btn.getAttribute("data-table-id"));
        var open = container.style.display === "none";
        container.style.display = open ? "block" : "none";
        btn.classList.toggle("expanded", open);
        if (open && !container.innerHTML.trim()) renderTable(tables[parseInt(btn.getAttribute("data-table-idx"), 10)], container, a);
      });
    });
  }

  function stdOf(t, h) { return (t.columns[h] || {}).Standard || null; }

  // Up to three grouping columns: the contrast, the measure, then named facets and the test kind,
  // each kept only where it groups rows within the levels above it (lightbox's rule).
  function groupingColumns(t, rows) {
    var cand = [];
    ["contrast", "measure"].forEach(function (term) {
      var i = t.headers.findIndex(function (h) { return stdOf(t, h) === term; });
      if (i >= 0) cand.push(i);
    });
    t.headers.forEach(function (h, i) { if (stdOf(t, h) === "facet") cand.push(i); });
    var tk = t.headers.findIndex(function (h) { return stdOf(t, h) === "test_kind"; });
    if (tk >= 0) cand.push(tk);
    var used = [];
    var count = function (cols) {
      var keys = {};
      rows.forEach(function (r) { keys[cols.map(function (i) { return r[i]; }).join("||")] = true; });
      return Object.keys(keys).length;
    };
    for (var idx of cand) {
      if (used.length >= 3) break;
      var parent = count(used), withIt = count(used.concat([idx]));
      // it must split some group above it, and leave groups of more than one row
      if (rows.length > 1 && withIt > parent && withIt < rows.length) used.push(idx);
    }
    return used;
  }
  // Each grouping column's values in the declared order (contrasts) or the order rows give them.
  function groupRanks(t, rows, groupCols, a) {
    return groupCols.map(function (gc) {
      var order = [];
      if (stdOf(t, t.headers[gc]) === "contrast") order = (a.contrasts || []).map(function (c) { return c.id; });
      rows.forEach(function (r) { if (order.indexOf(r[gc]) < 0) order.push(r[gc]); });
      var rank = {};
      order.forEach(function (v, i) { rank[v] = i; });
      return rank;
    });
  }
  function groupValueLabel(t, i, v, a) {
    var c = t.columns[t.headers[i]] || {};
    var names = { contrast: "Contrast", measure: "Measure", test_kind: "Test" };
    var name = c.Standard === "facet" ? (c.FacetName || t.headers[i]) : (names[c.Standard] || t.headers[i]);
    var value = c.Standard === "contrast" ? contrastLabel(a, v) : v === "" ? "(none)" : formatName(v);
    return formatName(name) + ": " + value;
  }

  function fmtNum(x, kind, raw) {
    if (/^-?\d+$/.test(raw)) return raw;
    if (kind === "p") return x < 0.001 ? x.toExponential(2) : x.toFixed(4);
    if (kind === "int") return Math.abs(x - Math.round(x)) < 0.01 ? x.toFixed(0) : x.toFixed(1);
    if (kind === "3") return x.toFixed(3);
    var ax = Math.abs(x);
    if (ax === 0) return "0";
    if (ax >= 100) return x.toFixed(1);
    if (ax >= 1) return x.toFixed(3);
    if (ax >= 0.001) return x.toFixed(4);
    return x.toExponential(2);
  }
  var NUM_KIND = {
    p_value: "p", p_uncorrected: "p", p_direction: "3", p_rope: "3", frac_significant: "3",
    effect_size: "3", effect_ci_low: "3", effect_ci_high: "3", stat: "3", subgroup_effect: "3",
    n: "int", n_a: "int", n_b: "int", df: "int", n_significant: "int", n_voxels: "int", subgroup_n: "int",
  };
  function cellHtml(t, h, v, a) {
    if (v === "" || v === null || v === undefined) return '<span class="muted">—</span>';
    var term = stdOf(t, h);
    if (term === "contrast") return esc(contrastLabel(a, v));
    if (term === "group_a" || term === "group_b" || term === "group") return esc(groupLabel(v));
    if (term === "significant" || term === "equivalent" || term === "effect_selected" || term === "qc_flag") {
      if (/^(true|1)$/i.test(v)) return '<strong class="yes">Yes</strong>';
      if (/^(false|0)$/i.test(v)) return '<span class="muted">No</span>';
    }
    if (/^-?\d*\.?\d+(e[+-]?\d+)?$/i.test(v)) {
      var x = parseFloat(v);
      if (isFinite(x)) return esc(fmtNum(x, NUM_KIND[term], v));
    }
    var lv = (t.columns[h] || {}).Levels;
    if (lv && lv[v]) return '<span title="' + esc(lv[v]) + '">' + esc(v) + "</span>";
    return esc(v);
  }

  function renderTable(t, container, a) {
    if (!t.headers.length) { container.innerHTML = '<p class="table-note">Empty table</p>'; return; }
    var rows = t.rows.map(function (r, n) { var c = r.slice(); c.n = n; return c; });
    var groupCols = groupingColumns(t, rows);
    // columns shown in the group headers need no column of their own, nor the contrast's label
    // when the contrasts are declared, nor a column every row leaves empty
    var empty = t.headers.map(function (h, i) { return rows.every(function (r) { return r[i] === ""; }); });
    var hidden = t.headers.map(function (h, i) {
      if (groupCols.indexOf(i) >= 0) return true;
      if (stdOf(t, h) === "contrast_label" && a.contrasts && a.contrasts.length) return true;
      return empty[i];
    });
    var nEmpty = empty.filter(function (e, i) { return e && groupCols.indexOf(i) < 0; }).length;
    if (groupCols.length) {
      var ranks = groupRanks(t, rows, groupCols, a);
      rows.sort(function (x, y) {
        for (var gi = 0; gi < groupCols.length; gi++) {
          var d = ranks[gi][x[groupCols[gi]]] - ranks[gi][y[groupCols[gi]]];
          if (d) return d;
        }
        return x.n - y.n;
      });
    }
    // what identifies a row first: its measure, element and facets; then the rest as written
    var lead = ["measure", "element", "facet"];
    var colOrder = t.headers.map(function (h, i) { return i; }).sort(function (x, y) {
      var rx = lead.indexOf(stdOf(t, t.headers[x])), ry = lead.indexOf(stdOf(t, t.headers[y]));
      if (rx < 0) rx = lead.length;
      if (ry < 0) ry = lead.length;
      return rx - ry || x - y;
    });
    var sig = t.headers.findIndex(function (h) { return stdOf(t, h) === "significant"; });
    var shown = hidden.filter(function (x) { return !x; }).length;
    var html = '<div class="table-tools"><input type="search" class="table-filter" placeholder="Filter rows">' +
      ' <a href="' + esc(t.path) + '" download>Download full CSV</a></div>';
    html += '<table class="sortable"><thead><tr>';
    colOrder.forEach(function (i) {
      var h = t.headers[i];
      if (hidden[i]) return;
      var c = t.columns[h] || {};
      var tip = [c.Description, c.Standard && "standard term: " + c.Standard, c.Units && "units: " + c.Units,
                 c.PKind && "p: " + c.PKind, c.EffectMeasure && "effect: " + c.EffectMeasure].filter(Boolean).join("\n");
      html += '<th class="' + (c.Standard ? "std" : "") + '" title="' + esc(tip) + '">' + esc(h) + '<span class="sort-indicator"></span></th>';
    });
    html += "</tr></thead><tbody>";
    var current = groupCols.map(function () { return null; });
    var links = t.links || {};
    rows.forEach(function (r) {
      groupCols.forEach(function (gc, gi) {
        if (r[gc] === current[gi]) return;
        current[gi] = r[gc];
        for (var k = gi + 1; k < current.length; k++) current[k] = null;
        var level = ["group-header-primary", "group-header-secondary", "group-header-tertiary"][gi];
        html += '</tbody><tbody class="group-headers"><tr class="' + level + '" data-sort-method="none"><td colspan="' +
          shown + '">' + esc(groupValueLabel(t, gc, r[gc], a)) + "</td></tr></tbody><tbody>";
      });
      var isSig = sig >= 0 && /^(true|1)$/i.test(r[sig]);
      html += "<tr" + (isSig ? ' class="significant"' : "") + ">";
      colOrder.forEach(function (i) {
        var h = t.headers[i];
        if (hidden[i]) return;
        var l = links[h] && links[h][r.n];
        if (l && l.length) {
          html += "<td>" + l.map(function (href) {
            return '<a href="' + esc(href) + '" target="_blank">' + esc(href.split("/").pop() || href) + "</a>";
          }).join(" ") + "</td>";
        } else {
          html += "<td>" + cellHtml(t, h, r[i], a) + "</td>";
        }
      });
      html += "</tr>";
    });
    html += "</tbody></table>";
    var note = [];
    if (t.total_rows > t.rows.length) note.push("Showing the first " + t.rows.length + " of " + t.total_rows + " rows");
    if (nEmpty) note.push(plural(nEmpty, "column") + " empty in every row, hidden");
    if (t.threshold && t.threshold.statement) note.push("Rows selected by: " + t.threshold.statement);
    if (note.length) html += '<p class="table-note">' + esc(note.join(" · ")) + "</p>";
    container.innerHTML = html;
    if (window.Tablesort) new window.Tablesort(container.querySelector("table"));
    var filter = container.querySelector(".table-filter");
    filter.addEventListener("input", function () {
      var q = filter.value.toLowerCase();
      container.querySelectorAll("tbody:not(.group-headers) tr").forEach(function (tr) {
        tr.style.display = !q || tr.textContent.toLowerCase().indexOf(q) >= 0 ? "" : "none";
      });
    });
  }

  /* ── Search: analyses, contrasts, figures and tables ── */
  function initSearch() {
    var input = document.getElementById("search-input");
    var timer = null;
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        var q = input.value.trim();
        if (q.length >= 2) location.hash = "#/search/" + encodeURIComponent(q);
        else if (!q) location.hash = "#/";
      }, 250);
    });
  }
  function renderSearch(query) {
    setBreadcrumb(["Search", query]);
    clearSelector();
    var q = query.toLowerCase();
    var hit = function (s) { return s !== undefined && s !== null && String(s).toLowerCase().indexOf(q) >= 0; };
    var links = [], figs = [];
    KEYS.forEach(function (k) {
      var a = A[k], d = designOf(a), href = "#" + analysisRoute(k);
      var where = d.label + " · " + domainLabel(domainOf(a));
      if (hit(a.title) || hit(a.id) || hit(a.description) || hit(a.domain) || hit(domainLabel(domainOf(a))) ||
          hit(d.label) || (a.measures || []).some(hit) || hit(a.task)) {
        links.push({ kind: "Analysis", label: a.title || a.id, sub: where, href: href });
      }
      (a.contrasts || []).forEach(function (c) {
        if (hit(c.label) || hit(c.id) || hit(c.tier)) links.push({ kind: "Contrast", label: c.label || c.id, sub: a.title || a.id, href: href });
      });
      a.tables.forEach(function (t) {
        if (hit(t.name) || hit(t.description)) links.push({ kind: "Table", label: t.name, sub: a.title || a.id, href: href });
      });
      a.figures.forEach(function (f) {
        if (hit(f.caption) || hit(f.path.split("/").pop())) figs.push(f);
      });
    });
    var html = '<h2 class="section-header">Search: "' + esc(query) + '"</h2>';
    html += '<p class="search-results-header">' + plural(links.length, "page") + ", " + plural(figs.length, "figure") + "</p>";
    if (links.length) {
      html += '<ul class="search-links">' + links.slice(0, 200).map(function (l) {
        return '<li><a href="' + esc(l.href) + '"><span class="search-kind">' + esc(l.kind) + "</span> " + esc(l.label) +
          "</a>" + (l.sub ? ' <span class="search-sub">' + esc(l.sub) + "</span>" : "") + "</li>";
      }).join("") + "</ul>";
    }
    if (figs.length) html += figureRows(figs.slice(0, 60), "search") +
      (figs.length > 60 ? '<p class="table-note">' + (figs.length - 60) + " more figures match; narrow the search.</p>" : "");
    setContent(html);
    initLightbox();
  }

  /* ── Small things ── */
  function bindTabs(root) {
    root.querySelectorAll(".tab-bar").forEach(function (bar) {
      var scope = bar.parentNode;
      bar.querySelectorAll(".tab-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var id = btn.getAttribute("data-tab");
          bar.querySelectorAll(".tab-btn").forEach(function (b) { b.classList.toggle("active", b === btn); });
          Array.prototype.forEach.call(scope.children, function (p) {
            if (p.classList.contains("tab-panel")) p.classList.toggle("active", p.getAttribute("data-panel") === id);
          });
        });
      });
    });
  }
  function bindMetricTabs(root) {
    root.querySelectorAll(".metric-tabs").forEach(function (bar) {
      var scope = bar.parentNode;
      bar.querySelectorAll(".metric-tab").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var id = btn.getAttribute("data-mtab");
          bar.querySelectorAll(".metric-tab").forEach(function (b) { b.classList.toggle("active", b === btn); });
          scope.querySelectorAll(".metric-panel").forEach(function (p) {
            p.classList.toggle("active", p.getAttribute("data-mpanel") === id);
          });
        });
      });
    });
  }
  function bindFigureGroups(root) {
    root.querySelectorAll(".fig-toggle-all").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var open = btn.getAttribute("data-open") === "1";
        (btn.closest(".figure-groups") || root).querySelectorAll("details.fig-group").forEach(function (d) { d.open = open; });
      });
    });
  }
  function initLightbox() {
    if (lightbox) lightbox.destroy();
    if (window.GLightbox) {
      lightbox = window.GLightbox({ selector: ".glightbox", touchNavigation: true, loop: true, zoomable: true, draggable: true });
    }
  }
  function initThemeToggle() {
    var saved = localStorage.getItem("neurobox-theme");
    if (saved) document.documentElement.setAttribute("data-theme", saved);
    else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
      document.documentElement.setAttribute("data-theme", "light");
    }
    document.getElementById("theme-toggle").addEventListener("click", function () {
      var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("neurobox-theme", next);
    });
  }
  function initKeyboard() {
    document.addEventListener("keydown", function (e) {
      var tag = document.activeElement && document.activeElement.tagName;
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA") {
        e.preventDefault();
        document.getElementById("search-input").focus();
      }
      if (e.key === "Escape") document.getElementById("search-input").blur();
    });
  }
  function setBreadcrumb(parts) {
    document.getElementById("breadcrumb").innerHTML = parts.map(function (p, i) {
      return (i ? "<span>&rsaquo;</span>" : "") + esc(p);
    }).join("");
  }
  function setContent(html) { document.getElementById("page").innerHTML = html; }
  function clearSelector() { document.getElementById("source-selector").innerHTML = ""; }
  function notFound(msg) {
    setBreadcrumb([msg]);
    clearSelector();
    setContent('<div class="empty-state"><p>' + esc(msg) + "</p></div>");
  }
})();
