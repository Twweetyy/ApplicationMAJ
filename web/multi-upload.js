const $ = (selector) => document.querySelector(selector);
const dataInput = $("#dataInput");
const metaInput = $("#metaInput");
const dataZone = $("#uploadData");
const metaZone = $("#uploadMeta");
const dataList = $("#dataFileList");
const metaList = $("#metaFileList");
const dataCount = $("#dataCount");
const metaCount = $("#metaCount");
const analyzeButton = $("#analyzeButton");
const reportSection = $("#reportSection");
const progressSection = $("#progressSection");
const downloadRow = $("#downloadRow");
const downloadButton = $("#downloadButton");
const newJobButton = $("#newJobButton");

const selected = { data: [], meta: [] };

// Fichiers de données attendus avec prédicats de détection robustes
const expectedDataFiles = [
  { label: "Périmètres MAS (requis)", test: (n) => n.includes("perimetresmas") },
  { label: "Évolution structure pop. (POP)", test: (n) => n.includes("evolstructpop") || n.includes("pop2023") },
  { label: "Diplômes et formation", test: (n) => n.includes("diplomesformation") || n.includes("dip2023") },
  { label: "Logement", test: (n) => n.includes("logement") || n.includes("log2023") },
  { label: "Activité des résidents", test: (n) => n.includes("activiteresidents") || n.includes("emp2023") },
  { label: "Couples, familles, ménages", test: (n) => n.includes("couplesfamillesmenages") || n.includes("men2023") },
  { label: "Filosofi Déciles (DEC)", test: (n) => n.includes("filo") && n.includes("dec") },
  { label: "Filosofi Revenus disp. (DISP)", test: (n) => n.includes("filo") && n.includes("disp") },
  { label: "Données CAF", test: (n) => n.includes("caf") },
  { label: "Données CNAM", test: (n) => n.includes("cnam") },
  { label: "Données DEFM", test: (n) => n.includes("defm") },
  { label: "Données RPLS", test: (n) => n.includes("rpls") },
  { label: "Recensement enfants (FD_INDCVI)", test: (n) => n.includes("indcvi") },
];

// Fichiers de métadonnées attendus
const expectedMetaFiles = [
  { label: "Méta Évolution structure pop.", test: (n) => n.includes("evolstructpop") },
  { label: "Méta Diplômes et formation", test: (n) => n.includes("diplomesformation") },
  { label: "Méta Logement", test: (n) => n.includes("logement") },
  { label: "Méta Activité des résidents", test: (n) => n.includes("activiteresidents") },
  { label: "Méta Couples, familles, ménages", test: (n) => n.includes("couplesfamillesmenages") },
  { label: "Méta Filosofi Déciles (DEC)", test: (n) => n.includes("filo") && n.includes("dec") },
  { label: "Méta Filosofi Revenus disp. (DISP)", test: (n) => n.includes("filo") && n.includes("disp") },
  { label: "Méta CAF", test: (n) => n.includes("caf") },
  { label: "Méta CNAM", test: (n) => n.includes("cnam") },
  { label: "Méta DEFM", test: (n) => n.includes("defm") },
  { label: "Méta RPLS", test: (n) => n.includes("rpls") },
  { label: "Varmod Enfants (varmod_indcvi)", test: (n) => n.includes("indcvi") },
];

let currentJobId = null;
let polling = false;

function normaliseNom(str) {
  return (str || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

function showError(element, message) {
  element.textContent = message;
  element.hidden = !message;
}

function setStep(active) {
  ["navSources", "navReport", "navResult"].forEach((id, index) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle("active", index === active);
  });
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} Ko`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} Mo`;
  return `${(bytes / 1024 ** 3).toFixed(2)} Go`;
}

function isMetaFile(name) {
  const lower = name.toLowerCase();
  return lower.startsWith("meta_") || lower.startsWith("varmod_");
}

function renderStatusList(containerId, expectedList, selectedFiles, title) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.className = "import-status-list";
  container.replaceChildren();

  const titleEl = document.createElement("p");
  titleEl.className = "import-status-title";
  titleEl.textContent = title;
  container.append(titleEl);

  const normalizedSelected = selectedFiles.map((f) => normaliseNom(f.name));

  for (const item of expectedList) {
    const isPresent = normalizedSelected.some((nom) => item.test(nom));
    const row = document.createElement("div");
    row.className = "import-status";

    const label = document.createElement("span");
    label.className = "status-label";
    label.textContent = item.label;

    const indicator = document.createElement("button");
    indicator.type = "button";
    indicator.className = `status-indicator${isPresent ? " success" : ""}`;
    indicator.textContent = isPresent ? "✅" : "🔴";
    indicator.disabled = !isPresent;
    indicator.title = isPresent ? `${item.label} : présent` : `${item.label} : manquant`;

    row.append(label, indicator);
    container.append(row);
  }
}

function updateImportStatus() {
  renderStatusList("dataStatusContainer", expectedDataFiles, selected.data, "Statut des données :");
  renderStatusList("metaStatusContainer", expectedMetaFiles, selected.meta, "Statut des métadonnées :");
}

function renderGroup(group, list, count, zone) {
  const files = selected[group];
  list.replaceChildren();
  count.textContent = files.length ? `${files.length} fichier${files.length > 1 ? "s" : ""}` : "Aucun fichier";
  zone.classList.toggle("success", files.length > 0);
  for (const file of files) {
    const row = document.createElement("li");
    row.className = "file-item";
    const name = document.createElement("span");
    name.className = "file-name";
    name.textContent = file.name;
    name.title = file.name;
    const size = document.createElement("span");
    size.className = "file-size";
    size.textContent = formatSize(file.size);
    const remove = document.createElement("button");
    remove.className = "remove-file";
    remove.type = "button";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Retirer ${file.name}`);
    remove.addEventListener("click", () => {
      selected[group] = files.filter((candidate) => candidate !== file);
      renderFiles();
    });
    row.append(name, size, remove);
    list.append(row);
  }
  $(group === "data" ? "#clearData" : "#clearMeta").disabled = files.length === 0;
}

function renderFiles() {
  renderGroup("data", dataList, dataCount, dataZone);
  renderGroup("meta", metaList, metaCount, metaZone);
  analyzeButton.disabled = selected.data.length === 0;
  updateImportStatus();
}

function addFiles(group, fileList) {
  const files = Array.from(fileList);
  const invalid = files.filter((file) => !file.name.toLowerCase().endsWith(".csv"));
  if (invalid.length) {
    showError($("#uploadError"), `Format CSV requis : ${invalid.map((file) => file.name).join(", ")}`);
    return;
  }
  const misplaced = files.filter((file) => isMetaFile(file.name) !== (group === "meta"));
  if (misplaced.length) {
    const target = group === "meta" ? "Données" : "Métadonnées & varmod";
    showError($("#uploadError"), `Déposez ${misplaced.map((file) => file.name).join(", ")} dans la zone ${target}.`);
    return;
  }
  const knownNames = new Set([...selected.data, ...selected.meta].map((file) => file.name.toLowerCase()));
  const duplicates = files.filter((file) => knownNames.has(file.name.toLowerCase()));
  if (duplicates.length) {
    showError($("#uploadError"), `Nom déjà sélectionné : ${duplicates.map((file) => file.name).join(", ")}.`);
    return;
  }
  showError($("#uploadError"), "");
  selected[group].push(...files);
  renderFiles();
}

function bindDropzone(zone, input, group) {
  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });
  input.addEventListener("change", (event) => {
    addFiles(group, event.target.files);
    input.value = "";
  });
  ["dragenter", "dragover"].forEach((type) => zone.addEventListener(type, (event) => {
    event.preventDefault();
    zone.classList.add("dragover");
  }));
  ["dragleave", "drop"].forEach((type) => zone.addEventListener(type, (event) => {
    event.preventDefault();
    zone.classList.remove("dragover");
  }));
  zone.addEventListener("drop", (event) => addFiles(group, event.dataTransfer.files));
}

function appendMessages(list, messages) {
  list.replaceChildren();
  for (const message of messages) {
    const item = document.createElement("li");
    item.textContent = `${message.fichier ? `${message.fichier} : ` : ""}${message.message || message}`;
    list.append(item);
  }
}

function showReport(job) {
  const report = job.rapport;
  reportSection.hidden = false;
  setStep(1);
  const status = $("#reportStatus");
  status.className = `status-badge${report.statut === "erreur" ? " error" : report.statut === "attention" ? " warning" : ""}`;
  status.textContent = report.statut === "erreur" ? "Bloqué" : report.statut === "attention" ? "À vérifier" : "Prêt";
  $("#reportSummary").replaceChildren();
  [
    [report.sources.filter((source) => source.role === "theme").length, "thèmes"],
    [report.sources.filter((source) => source.role === "perimetre").length, "périmètre"],
    [report.sources.filter((source) => source.role === "microdonnees_enfants").length, "fichier enfants"],
  ].forEach(([value, label]) => {
    const chip = document.createElement("span");
    chip.className = "summary-chip";
    chip.textContent = `${value} ${label}`;
    $("#reportSummary").append(chip);
  });
  $("#sourceRows").replaceChildren();
  report.sources.forEach((source) => {
    const row = document.createElement("tr");
    const metaLabel = source.role === "perimetre" ? "-" : source.meta ? "Associée" : "Absente";
    [source.fichier, source.theme || source.role, source.millesime || "-", metaLabel,
      source.colonnes_non_documentees?.length ? source.colonnes_non_documentees.join(", ") : "-"].forEach((value, index) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      if (index === 3 && source.role !== "perimetre") cell.className = source.meta ? "meta-present" : "meta-missing";
      row.append(cell);
    });
    $("#sourceRows").append(row);
  });
  appendMessages($("#errorList"), report.erreurs || []);
  $("#errorGroup").hidden = !(report.erreurs || []).length;
  appendMessages($("#warningList"), report.avertissements || []);
  $("#warningGroup").hidden = !(report.avertissements || []).length;
  $("#ignoredList").replaceChildren();
  (report.fichiers_ignores || []).forEach((file) => {
    const item = document.createElement("li");
    item.textContent = file;
    $("#ignoredList").append(item);
  });
  $("#ignoredGroup").hidden = !(report.fichiers_ignores || []).length;
  $("#clearGroup").hidden = Boolean((report.erreurs || []).length || (report.avertissements || []).length);
  const blocked = job.status === "invalid" || report.statut === "erreur";
  $("#generateButton").disabled = blocked;
  $("#generationNote").textContent = blocked ? "Corrigez les erreurs bloquantes et déposez à nouveau le lot." : "Les avertissements n’empêchent pas la génération.";
}

function analyzeFiles() {
  if (!selected.data.length) return;
  analyzeButton.disabled = true;
  showError($("#uploadError"), "");

  const analyzeProgress = $("#analyzeProgress");
  const analyzeProgressBar = $("#analyzeProgressBar");
  const analyzeProgressText = $("#analyzeProgressText");

  analyzeProgress.hidden = false;
  analyzeProgressBar.style.width = "0%";
  analyzeProgressBar.style.animation = "none";
  analyzeProgressText.textContent = "Préparation de l'envoi…";
  analyzeButton.querySelector("span:first-child").textContent = "Contrôle en cours…";

  const form = new FormData();
  [...selected.data, ...selected.meta].forEach((file) => form.append("files", file, file.name));

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/jobs");

  xhr.upload.addEventListener("progress", (event) => {
    if (event.lengthComputable) {
      const percent = Math.min(100, Math.round((event.loaded / event.total) * 100));
      analyzeProgressBar.style.width = `${percent}%`;
      const loadedStr = formatSize(event.loaded);
      const totalStr = formatSize(event.total);
      if (percent < 100) {
        analyzeProgressText.textContent = `Téléversement des fichiers : ${percent}% (${loadedStr} / ${totalStr})…`;
      } else {
        analyzeProgressText.textContent = "Fichiers téléversés. Analyse et pré-contrôle en cours…";
        analyzeProgressBar.style.animation = "progress 1.8s ease-in-out infinite";
      }
    } else {
      analyzeProgressText.textContent = "Téléversement des fichiers en cours…";
      analyzeProgressBar.style.animation = "progress 1.8s ease-in-out infinite";
    }
  });

  xhr.addEventListener("load", () => {
    analyzeProgress.hidden = true;
    analyzeButton.querySelector("span:first-child").textContent = "Analyser le lot";
    analyzeButton.disabled = selected.data.length === 0;

    let result;
    try {
      result = JSON.parse(xhr.responseText);
    } catch (_) {
      result = { detail: xhr.responseText || "Erreur serveur inconnue." };
    }

    if (xhr.status >= 200 && xhr.status < 300) {
      currentJobId = result.id;
      if (selected.data.length) dataZone.classList.add("success");
      if (selected.meta.length) metaZone.classList.add("success");
      showReport(result);
      reportSection.scrollIntoView({ behavior: "smooth", block: "start" });
    } else {
      showError($("#uploadError"), result.detail || "Le contrôle du lot a échoué.");
    }
  });

  xhr.addEventListener("error", () => {
    analyzeProgress.hidden = true;
    analyzeButton.querySelector("span:first-child").textContent = "Analyser le lot";
    analyzeButton.disabled = selected.data.length === 0;
    showError($("#uploadError"), "Impossible de communiquer avec le serveur.");
  });

  xhr.addEventListener("abort", () => {
    analyzeProgress.hidden = true;
    analyzeButton.querySelector("span:first-child").textContent = "Analyser le lot";
    analyzeButton.disabled = selected.data.length === 0;
  });

  xhr.send(form);
}

function showGenerationState(status, error = "", warnings = []) {
  progressSection.hidden = false;
  const finished = status === "done" || status === "done_with_warnings";
  setStep(finished ? 2 : 1);
  progressSection.classList.toggle("complete", finished);
  progressSection.classList.toggle("failed", status === "failed" || status === "invalid");
  $("#progressTitle").textContent = status === "done_with_warnings" ? "Classeur généré avec avertissements"
    : status === "done" ? "Classeur prêt"
      : status === "failed" || status === "invalid" ? "Génération interrompue" : "Préparation du classeur";
  $("#progressIndicator").innerHTML = finished ? "<i></i> Terminé"
    : status === "failed" || status === "invalid" ? "<i></i> Échec" : "<i></i> En cours";
  $("#progressCopy").textContent = status === "done_with_warnings"
    ? "Certaines formules n’ont pas pu être calculées. Vérifiez les détails avant d’utiliser le classeur."
    : status === "done" ? "Le classeur a été généré à partir du modèle BDDMAS."
      : status === "failed" || status === "invalid" ? "Le classeur n’a pas été généré. Consultez le message ci-dessous."
        : "Traitement local des fichiers et génération du classeur.";
  showError($("#generationError"), error || warnings.join("\n"));
  downloadRow.hidden = !finished;
  if (finished && currentJobId) downloadButton.href = `/api/jobs/${currentJobId}/download`;
}

const LIBELLES_DECISION = {
  correspondance: "Rattachée à un en-tête existant",
  nouvelle: "Nouvelle colonne",
  non_resolue: "À vérifier : gardée sous son nom",
};

function showColonnesAuto(decisions) {
  const bloc = $("#colonnesAuto");
  const lignes = $("#colonnesAutoRows");
  lignes.replaceChildren();
  bloc.hidden = !decisions.length;
  if (!decisions.length) return;
  const aVerifier = decisions.filter((decision) => decision.decision === "non_resolue").length;
  $("#colonnesAutoNote").textContent =
    `${decisions.length} colonne(s) inconnue(s) du modèle traitée(s) automatiquement` +
    (aVerifier ? `, dont ${aVerifier} à vérifier.` : ".") +
    " Corrections possibles dans dictionnaires/correspondances_auto.yml (methode: manuel).";
  for (const decision of decisions) {
    const ligne = document.createElement("tr");
    const confiance = decision.confiance == null ? "-" : `${Math.round(decision.confiance * 100)} %`;
    const methode = decision.methode === "llm" ? " (IA)" : decision.methode === "approchee" ? " (sans IA)" : "";
    [decision.onglet, decision.libelle_source, decision.entete,
      `${LIBELLES_DECISION[decision.decision] || decision.decision}${methode}`, confiance].forEach((valeur, index) => {
      const cellule = document.createElement("td");
      cellule.textContent = valeur;
      if (index === 3) cellule.className = decision.decision === "non_resolue" ? "meta-missing" : "meta-present";
      ligne.append(cellule);
    });
    if (decision.justification) ligne.title = decision.justification;
    lignes.append(ligne);
  }
}

async function pollJob() {
  if (polling) return;
  polling = true;
  try {
    while (currentJobId) {
      const response = await fetch(`/api/jobs/${currentJobId}`);
      const job = await response.json();
      if (!response.ok) throw new Error(job.detail || "Impossible de suivre le traitement.");
      if (job.status === "done" || job.status === "done_with_warnings") {
        showGenerationState(job.status, "", job.avertissements_calcul || []);
        showColonnesAuto(job.colonnes_auto || []);
        break;
      }
      if (job.status === "failed" || job.status === "invalid") {
        showGenerationState(job.status, job.erreur || "Le lot ne peut pas être généré.");
        break;
      }
      showGenerationState(job.status);
      await new Promise((resolve) => window.setTimeout(resolve, 2200));
    }
  } catch (error) {
    showGenerationState("failed", error.message || "La connexion au serveur a été interrompue.");
  } finally {
    polling = false;
  }
}

async function startGeneration() {
  if (!currentJobId) return;
  $("#generateButton").disabled = true;
  showGenerationState("queued");
  setStep(2);
  progressSection.scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    const response = await fetch(`/api/jobs/${currentJobId}/generate`, { method: "POST" });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "La génération n’a pas pu démarrer.");
    showGenerationState(result.status);
    pollJob();
  } catch (error) {
    showGenerationState("failed", error.message || "La génération n’a pas pu démarrer.");
    $("#generateButton").disabled = false;
  }
}

async function resetJob() {
  if (currentJobId) await fetch(`/api/jobs/${currentJobId}`, { method: "DELETE" }).catch(() => {});
  currentJobId = null;
  selected.data = [];
  selected.meta = [];
  dataInput.value = "";
  metaInput.value = "";
  renderFiles();
  dataZone.classList.remove("success");
  metaZone.classList.remove("success");
  reportSection.hidden = true;
  progressSection.hidden = true;
  showColonnesAuto([]);
  $("#analyzeProgress").hidden = true;
  showError($("#uploadError"), "");
  showError($("#generationError"), "");
  $("#generateButton").disabled = true;
  setStep(0);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function clearSelectedGroup(group) {
  selected[group] = [];
  (group === "data" ? dataInput : metaInput).value = "";
  showError($("#uploadError"), "");
  renderFiles();
}

bindDropzone(dataZone, dataInput, "data");
bindDropzone(metaZone, metaInput, "meta");
$("#clearData").addEventListener("click", () => clearSelectedGroup("data"));
$("#clearMeta").addEventListener("click", () => clearSelectedGroup("meta"));
analyzeButton.addEventListener("click", analyzeFiles);
$("#generateButton").addEventListener("click", startGeneration);
newJobButton.addEventListener("click", resetJob);
renderFiles();
