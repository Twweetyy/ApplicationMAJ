const fileInput = document.querySelector("#fileInput");
const dropzone = document.querySelector("#dropzone");
const fileList = document.querySelector("#fileList");
const selectionCount = document.querySelector("#selectionCount");
const analyzeButton = document.querySelector("#analyzeButton");
const uploadError = document.querySelector("#uploadError");
const reportSection = document.querySelector("#reportSection");
const reportStatus = document.querySelector("#reportStatus");
const reportSummary = document.querySelector("#reportSummary");
const sourceRows = document.querySelector("#sourceRows");
const errorGroup = document.querySelector("#errorGroup");
const errorList = document.querySelector("#errorList");
const warningGroup = document.querySelector("#warningGroup");
const warningList = document.querySelector("#warningList");
const ignoredGroup = document.querySelector("#ignoredGroup");
const ignoredList = document.querySelector("#ignoredList");
const clearGroup = document.querySelector("#clearGroup");
const generateButton = document.querySelector("#generateButton");
const progressSection = document.querySelector("#progressSection");
const progressTitle = document.querySelector("#progressTitle");
const progressIndicator = document.querySelector("#progressIndicator");
const progressCopy = document.querySelector("#progressCopy");
const generationError = document.querySelector("#generationError");
const downloadRow = document.querySelector("#downloadRow");
const downloadButton = document.querySelector("#downloadButton");
const newJobButton = document.querySelector("#newJobButton");
const clearFilesButton = document.querySelector("#clearFiles");

let selectedFiles = [];
let currentJobId = null;
let polling = false;

function humanSize(bytes) {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} Ko`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} Go`;
}

function isMetadata(name) {
  const normalized = name.toLowerCase();
  return normalized.startsWith("meta_") || normalized.startsWith("varmod_");
}

function setError(element, message) {
  element.textContent = message;
  element.hidden = !message;
}

function setStep(active) {
  const steps = ["stepUpload", "stepCheck", "stepResult"];
  steps.forEach((id, index) => {
    const step = document.getElementById(id);
    step.classList.toggle("active", index === active);
    step.classList.toggle("complete", index < active);
  });
}

function renderFiles() {
  fileList.replaceChildren();
  selectionCount.textContent = selectedFiles.length
    ? `${selectedFiles.length} fichier${selectedFiles.length > 1 ? "s" : ""} sélectionné${selectedFiles.length > 1 ? "s" : ""}`
    : "Aucun fichier sélectionné";
  clearFilesButton.disabled = selectedFiles.length === 0;
  analyzeButton.disabled = selectedFiles.length === 0;

  for (const file of selectedFiles) {
    const item = document.createElement("li");
    item.className = "file-item";
    const name = document.createElement("span");
    name.className = "file-name";
    name.textContent = file.name;
    const kind = document.createElement("span");
    kind.className = "file-kind";
    kind.textContent = isMetadata(file.name) ? "Méta" : "Donnée";
    const size = document.createElement("span");
    size.className = "file-size";
    size.textContent = humanSize(file.size);
    item.append(name, kind, size);
    fileList.append(item);
  }
}

function mergeFiles(files) {
  const known = new Set(selectedFiles.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
  const incoming = Array.from(files).filter((file) => file.name.toLowerCase().endsWith(".csv"));
  for (const file of incoming) {
    const key = `${file.name}:${file.size}:${file.lastModified}`;
    if (!known.has(key)) selectedFiles.push(file);
  }
  renderFiles();
}

function appendListMessages(list, messages, messageField = "message") {
  list.replaceChildren();
  for (const entry of messages) {
    const item = document.createElement("li");
    const fileName = entry.fichier ? `${entry.fichier} : ` : "";
    item.textContent = `${fileName}${entry[messageField] || entry}`;
    list.append(item);
  }
}

function renderReport(job) {
  const report = job.rapport;
  reportSection.hidden = false;
  setStep(1);
  reportStatus.className = `status-badge${report.statut === "erreur" ? " error" : report.statut === "attention" ? " warning" : ""}`;
  reportStatus.textContent = report.statut === "erreur" ? "Bloqué" : report.statut === "attention" ? "À vérifier" : "Prêt";

  reportSummary.replaceChildren();
  const counts = [
    [`${report.sources.filter((source) => source.role === "theme").length}`, "thèmes"],
    [`${report.sources.filter((source) => source.role === "perimetre").length}`, "périmètre"],
    [`${report.sources.filter((source) => source.role === "microdonnees_enfants").length}`, "fichier enfants"],
  ];
  for (const [value, label] of counts) {
    const chip = document.createElement("span");
    chip.className = "summary-chip";
    chip.textContent = `${value} ${label}`;
    reportSummary.append(chip);
  }

  sourceRows.replaceChildren();
  for (const source of report.sources) {
    const row = document.createElement("tr");
    const metaLabel = source.role === "perimetre"
      ? "-"
      : source.meta ? "Associée" : "Absente";
    const cells = [
      source.fichier,
      source.theme || source.role,
      source.millesime || "-",
      metaLabel,
      source.colonnes_non_documentees?.length ? source.colonnes_non_documentees.join(", ") : "-",
    ];
    cells.forEach((value, index) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      if (index === 3 && source.role !== "perimetre") {
        cell.className = source.meta ? "meta-present" : "meta-missing";
      }
      row.append(cell);
    });
    sourceRows.append(row);
  }

  appendListMessages(errorList, report.erreurs || []);
  errorGroup.hidden = !(report.erreurs || []).length;
  appendListMessages(warningList, report.avertissements || []);
  warningGroup.hidden = !(report.avertissements || []).length;
  ignoredList.replaceChildren();
  for (const ignored of report.fichiers_ignores || []) {
    const item = document.createElement("li");
    item.textContent = ignored;
    ignoredList.append(item);
  }
  ignoredGroup.hidden = !(report.fichiers_ignores || []).length;
  clearGroup.hidden = Boolean((report.erreurs || []).length || (report.avertissements || []).length);
  generateButton.disabled = job.status === "invalid" || report.statut === "erreur";
  document.querySelector("#generationNote").textContent = generateButton.disabled
    ? "Corrigez les erreurs bloquantes et déposez à nouveau le lot."
    : "Les avertissements n’empêchent pas la génération.";
}

async function analyzeFiles() {
  if (!selectedFiles.length) return;
  analyzeButton.disabled = true;
  setError(uploadError, "");
  analyzeButton.querySelector("span:first-child").textContent = "Contrôle en cours…";
  const form = new FormData();
  selectedFiles.forEach((file) => form.append("files", file, file.name));

  try {
    const response = await fetch("/api/jobs", { method: "POST", body: form });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Le contrôle du lot a échoué.");
    currentJobId = payload.id;
    renderReport(payload);
    reportSection.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setError(uploadError, error.message || "Impossible d’analyser les fichiers.");
  } finally {
    analyzeButton.querySelector("span:first-child").textContent = "Analyser le lot";
    analyzeButton.disabled = selectedFiles.length === 0;
  }
}

function showGenerationState(status, error = "", warnings = []) {
  progressSection.hidden = false;
  const finished = status === "done" || status === "done_with_warnings";
  setStep(finished ? 2 : 1);
  progressSection.classList.toggle("complete", finished);
  progressSection.classList.toggle("failed", status === "failed" || status === "invalid");
  progressTitle.textContent = status === "done_with_warnings"
    ? "Classeur généré avec avertissements"
    : status === "done" ? "Classeur prêt" : status === "failed" || status === "invalid" ? "Génération interrompue" : "Préparation du classeur";
  progressIndicator.innerHTML = finished ? "<i></i> Terminé" : status === "failed" || status === "invalid" ? "<i></i> Échec" : "<i></i> En cours";
  progressCopy.textContent = status === "done_with_warnings"
    ? "Certaines formules n’ont pas pu être calculées. Vérifiez les détails avant d’utiliser le classeur."
    : status === "done"
      ? "Le classeur a été généré à partir du modèle BDDMAS."
    : status === "failed" || status === "invalid"
      ? "Le classeur n’a pas été généré. Consultez le message ci-dessous."
      : "Traitement local des données et génération du classeur. Cette étape peut prendre quelques minutes.";
  const details = error || warnings.join("\n");
  setError(generationError, details);
  downloadRow.hidden = !finished;
  if (finished && currentJobId) downloadButton.href = `/api/jobs/${currentJobId}/download`;
}

async function fetchJob() {
  const response = await fetch(`/api/jobs/${currentJobId}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "Impossible de suivre le traitement.");
  return payload;
}

async function pollJob() {
  if (polling) return;
  polling = true;
  try {
    while (currentJobId) {
      const job = await fetchJob();
      if (job.status === "done" || job.status === "done_with_warnings") {
        showGenerationState(job.status, "", job.avertissements_calcul || []);
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
  generateButton.disabled = true;
  progressSection.hidden = false;
  showGenerationState("queued");
  setStep(2);
  progressSection.scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    const response = await fetch(`/api/jobs/${currentJobId}/generate`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "La génération n’a pas pu démarrer.");
    showGenerationState(payload.status);
    pollJob();
  } catch (error) {
    showGenerationState("failed", error.message || "La génération n’a pas pu démarrer.");
    generateButton.disabled = false;
  }
}

async function resetJob() {
  if (currentJobId) {
    await fetch(`/api/jobs/${currentJobId}`, { method: "DELETE" }).catch(() => {});
  }
  currentJobId = null;
  selectedFiles = [];
  fileInput.value = "";
  renderFiles();
  reportSection.hidden = true;
  progressSection.hidden = true;
  uploadError.hidden = true;
  generationError.hidden = true;
  generateButton.disabled = true;
  setStep(0);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

fileInput.addEventListener("change", (event) => mergeFiles(event.target.files));
for (const eventName of ["dragenter", "dragover"]) {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("dragover");
  });
}
for (const eventName of ["dragleave", "drop"]) {
  dropzone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("dragover");
  });
}
dropzone.addEventListener("drop", (event) => mergeFiles(event.dataTransfer.files));
dropzone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});
clearFilesButton.addEventListener("click", () => {
  selectedFiles = [];
  fileInput.value = "";
  renderFiles();
});
analyzeButton.addEventListener("click", analyzeFiles);
generateButton.addEventListener("click", startGeneration);
newJobButton.addEventListener("click", resetJob);

renderFiles();
