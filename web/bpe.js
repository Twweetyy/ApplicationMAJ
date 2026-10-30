const $ = (selector) => document.querySelector(selector);
const selected = { source: null, varmod: null };
let perimetre = "roubaix";
let currentJobId = null;

const NOTES = {
  roubaix: "Les équipements de Roubaix (DEPCOM 59512) sont gardés, avec libellé IRIS, secteur mairie, quartier historique et grand quartier.",
  mel: "Les équipements des 95 communes de la MEL sont gardés ; le récapitulatif compte les équipements par commune.",
};

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} Ko`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} Mo`;
  return `${(bytes / 1024 ** 3).toFixed(2)} Go`;
}

function showError(element, message) {
  element.textContent = message;
  element.hidden = !message;
}

function renderSlot(slot) {
  const file = selected[slot];
  const list = $(`#${slot}List`);
  list.replaceChildren();
  $(`#${slot}Zone`).classList.toggle("success", Boolean(file));
  $(`#${slot}Count`).textContent = file ? "1 fichier" : slot === "source" ? "Aucun fichier" : "Varmod BPE 2025 (par défaut)";
  if (file) {
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
      selected[slot] = null;
      renderSlot(slot);
    });
    row.append(name, size, remove);
    list.append(row);
  }
  $("#generateButton").disabled = !selected.source;
}

function setFile(slot, files) {
  const file = files && files[0];
  if (!file) return;
  const extensions = slot === "source" ? [".csv", ".parquet"] : [".csv"];
  if (!extensions.some((ext) => file.name.toLowerCase().endsWith(ext))) {
    showError($("#uploadError"), `Format ${slot === "source" ? "CSV ou Parquet" : "CSV"} requis : ${file.name}`);
    return;
  }
  showError($("#uploadError"), "");
  selected[slot] = file;
  renderSlot(slot);
}

function bindDropzone(slot) {
  const zone = $(`#${slot}Zone`);
  const input = $(`#${slot}Input`);
  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });
  input.addEventListener("change", (event) => {
    setFile(slot, event.target.files);
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
  zone.addEventListener("drop", (event) => setFile(slot, event.dataTransfer.files));
}

function setPerimetre(valeur) {
  perimetre = valeur;
  document.querySelectorAll("[data-perimetre]").forEach((tab) => {
    const actif = tab.dataset.perimetre === valeur;
    tab.classList.toggle("active", actif);
    tab.setAttribute("aria-checked", String(actif));
  });
  $("#perimetreNote").textContent = NOTES[valeur];
}

function setProgress(state, title, copy) {
  const section = $("#progressSection");
  section.hidden = false;
  section.classList.toggle("complete", state === "done");
  section.classList.toggle("failed", state === "failed");
  $("#progressTitle").textContent = title;
  $("#progressCopy").textContent = copy;
  $("#progressIndicator").lastChild.textContent = state === "done" ? " Terminé" : state === "failed" ? " Échec" : " En cours";
}

function showResult(job) {
  const resume = job.resume;
  const summary = $("#resultSummary");
  summary.replaceChildren();
  const chips = [
    `${resume.equipements.toLocaleString("fr-FR")} équipements`,
    `BPE ${resume.annee}`,
    `Périmètre ${resume.perimetre}`,
    resume.perimetre === "MEL" ? `${resume.communes} communes` : `${resume.non_localises_iris} non localisés à l'IRIS`,
  ];
  for (const text of chips) {
    const chip = document.createElement("span");
    chip.className = "summary-chip";
    chip.textContent = text;
    summary.append(chip);
  }
  summary.hidden = false;

  showColonnes(resume.colonnes_nouvelles || [], resume.colonnes_absentes || []);

  const rows = $("#domainRows");
  rows.replaceChildren();
  for (const domaine of resume.domaines) {
    const row = document.createElement("tr");
    for (const value of [domaine.code, domaine.libelle, domaine.equipements.toLocaleString("fr-FR")]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    rows.append(row);
  }
  $("#domainTable").hidden = false;
  $("#downloadButton").href = `/api/bpe/jobs/${job.id}/download`;
  $("#downloadRow").hidden = false;
}

function fillList(list, colonnes, bloc) {
  list.replaceChildren();
  for (const colonne of colonnes) {
    const item = document.createElement("li");
    item.textContent = `${colonne.code} : ${colonne.en_tete || colonne.libelle}`;
    list.append(item);
  }
  bloc.hidden = colonnes.length === 0;
}

function showColonnes(nouvelles, absentes) {
  const notice = $("#colonnesNotice");
  notice.hidden = nouvelles.length === 0 && absentes.length === 0;
  if (notice.hidden) return;
  const parties = [];
  if (nouvelles.length) parties.push(`${nouvelles.length} nouvelle${nouvelles.length > 1 ? "s" : ""} colonne${nouvelles.length > 1 ? "s" : ""}`);
  if (absentes.length) parties.push(`${absentes.length} colonne${absentes.length > 1 ? "s" : ""} absente${absentes.length > 1 ? "s" : ""}`);
  $("#colonnesNoticeText").textContent = `Ce millésime diffère des colonnes connues : ${parties.join(" et ")}. Vérifiez avant de publier.`;
  fillList($("#colonnesNouvelles"), nouvelles, $("#colonnesNouvellesBloc"));
  fillList($("#colonnesAbsentes"), absentes, $("#colonnesAbsentesBloc"));
}

async function pollJob() {
  try {
    const response = await fetch(`/api/bpe/jobs/${currentJobId}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.detail || "Traitement introuvable.");
    if (job.status === "done") {
      setProgress("done", "Classeur prêt", "Le classeur BPE a été généré.");
      showResult(job);
      return;
    }
    if (job.status === "failed") {
      setProgress("failed", "Génération impossible", "Le classeur n'a pas pu être produit.");
      showError($("#generationError"), job.erreur || "Erreur inconnue.");
      $("#downloadRow").hidden = false;
      $("#downloadButton").hidden = true;
      return;
    }
    setProgress("processing", "Préparation du classeur", "Filtre du périmètre, traduction des codes Insee et écriture du classeur…");
    setTimeout(pollJob, 1500);
  } catch (error) {
    setProgress("failed", "Génération impossible", "Le serveur ne répond pas.");
    showError($("#generationError"), error.message);
  }
}

function startGeneration() {
  const form = new FormData();
  form.append("source", selected.source);
  if (selected.varmod) form.append("varmod", selected.varmod);
  form.append("perimetre", perimetre);

  $("#generateButton").disabled = true;
  showError($("#generationError"), "");
  $("#resultSummary").hidden = true;
  $("#domainTable").hidden = true;
  $("#colonnesNotice").hidden = true;
  $("#downloadRow").hidden = true;
  $("#downloadButton").hidden = false;
  setProgress("processing", "Envoi du fichier", "Envoi du fichier au serveur local.");

  // XMLHttpRequest pour suivre l'envoi d'un fichier national volumineux
  const request = new XMLHttpRequest();
  request.open("POST", "/api/bpe/jobs");
  request.upload.addEventListener("progress", (event) => {
    if (event.lengthComputable) {
      const percent = Math.round((event.loaded / event.total) * 100);
      $("#progressCopy").textContent = `Envoi du fichier : ${percent} % (${formatSize(event.loaded)} sur ${formatSize(event.total)})`;
    }
  });
  request.addEventListener("load", () => {
    let job = {};
    try { job = JSON.parse(request.responseText); } catch { /* réponse non JSON */ }
    if (request.status >= 400) {
      setProgress("failed", "Envoi refusé", "Le fichier n'a pas été accepté.");
      showError($("#generationError"), job.detail || `Erreur ${request.status}`);
      $("#generateButton").disabled = !selected.source;
      return;
    }
    currentJobId = job.id;
    pollJob();
  });
  request.addEventListener("error", () => {
    setProgress("failed", "Envoi impossible", "Le serveur ne répond pas.");
    $("#generateButton").disabled = !selected.source;
  });
  request.send(form);
}

async function resetJob() {
  if (currentJobId) await fetch(`/api/bpe/jobs/${currentJobId}`, { method: "DELETE" }).catch(() => {});
  currentJobId = null;
  selected.source = null;
  selected.varmod = null;
  renderSlot("source");
  renderSlot("varmod");
  $("#progressSection").hidden = true;
  showError($("#generationError"), "");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

bindDropzone("source");
bindDropzone("varmod");
document.querySelectorAll("[data-perimetre]").forEach((tab) => tab.addEventListener("click", () => setPerimetre(tab.dataset.perimetre)));
$("#generateButton").addEventListener("click", startGeneration);
$("#newJobButton").addEventListener("click", resetJob);
