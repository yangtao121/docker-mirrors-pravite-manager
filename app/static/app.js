const state = {
  repositories: [],
  filteredRepositories: [],
  nextCursor: null,
  selectedRepository: null,
  activeJobId: null,
  jobPollTimer: null,
  localImages: [],
  selectedLocalRefs: new Set(),
  detectedArch: "unknown",
};

const dom = {
  healthDot: document.querySelector("#healthDot"),
  healthText: document.querySelector("#healthText"),
  repoSearch: document.querySelector("#repoSearch"),
  repoList: document.querySelector("#repoList"),
  loadMoreBtn: document.querySelector("#loadMoreBtn"),
  refreshReposBtn: document.querySelector("#refreshReposBtn"),
  repoTitle: document.querySelector("#repoTitle"),
  repoMeta: document.querySelector("#repoMeta"),
  refreshTagsBtn: document.querySelector("#refreshTagsBtn"),
  tagTableBody: document.querySelector("#tagTableBody"),
  syncForm: document.querySelector("#syncForm"),
  sourceImage: document.querySelector("#sourceImage"),
  targetRepo: document.querySelector("#targetRepo"),
  targetTag: document.querySelector("#targetTag"),
  syncBtn: document.querySelector("#syncBtn"),
  refreshLocalBtn: document.querySelector("#refreshLocalBtn"),
  localHint: document.querySelector("#localHint"),
  archMode: document.querySelector("#archMode"),
  archValue: document.querySelector("#archValue"),
  prefixMode: document.querySelector("#prefixMode"),
  prefixValue: document.querySelector("#prefixValue"),
  selectAllLocalBtn: document.querySelector("#selectAllLocalBtn"),
  clearLocalBtn: document.querySelector("#clearLocalBtn"),
  pushLocalBtn: document.querySelector("#pushLocalBtn"),
  cleanupLocalTag: document.querySelector("#cleanupLocalTag"),
  cleanupRegistrySourceTag: document.querySelector("#cleanupRegistrySourceTag"),
  localImageList: document.querySelector("#localImageList"),
  jobStatusChip: document.querySelector("#jobStatusChip"),
  jobLogBox: document.querySelector("#jobLogBox"),
  jobList: document.querySelector("#jobList"),
  refreshJobsBtn: document.querySelector("#refreshJobsBtn"),
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = payload.detail || JSON.stringify(payload);
    } catch {
      // Keep fallback detail.
    }
    throw new Error(detail);
  }
  return response.json();
}

function formatBytes(bytes) {
  if (typeof bytes !== "number" || Number.isNaN(bytes)) {
    return "-";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(2)} ${units[unit]}`;
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

function shortDigest(digest) {
  if (!digest) {
    return "-";
  }
  if (digest.length <= 22) {
    return digest;
  }
  return `${digest.slice(0, 16)}...${digest.slice(-6)}`;
}

function setHealth(healthy, text) {
  dom.healthText.textContent = text;
  dom.healthDot.style.background = healthy ? "var(--ok)" : "var(--danger)";
}

function updateLocalHint() {
  const selected = state.selectedLocalRefs.size;
  dom.localHint.textContent = `Detected arch: ${state.detectedArch} | Selected: ${selected} | Total local images: ${state.localImages.length}`;
}

async function refreshHealth() {
  try {
    const result = await request("/api/health");
    state.detectedArch = result.detected_arch || state.detectedArch;
    updateLocalHint();
    const message = result.registry_healthy
      ? `Registry Online (${result.registry_push_host})`
      : `Registry Unreachable (${result.registry_push_host})`;
    setHealth(Boolean(result.registry_healthy), message);
  } catch (error) {
    setHealth(false, `Health check failed: ${error.message}`);
  }
}

function applyRepoFilter() {
  const keyword = dom.repoSearch.value.trim().toLowerCase();
  state.filteredRepositories = state.repositories.filter((item) =>
    item.toLowerCase().includes(keyword),
  );
  renderRepositoryList();
}

function renderRepositoryList() {
  dom.repoList.innerHTML = "";
  if (state.filteredRepositories.length === 0) {
    dom.repoList.innerHTML = `<li class="repo-empty">No repositories found.</li>`;
    return;
  }
  for (const repo of state.filteredRepositories) {
    const item = document.createElement("li");
    item.className = `repo-item${repo === state.selectedRepository ? " active" : ""}`;
    item.textContent = repo;
    item.addEventListener("click", () => selectRepository(repo));
    dom.repoList.appendChild(item);
  }
}

function setRepoMeta(message) {
  dom.repoMeta.textContent = message;
}

async function loadRepositories({ append = false } = {}) {
  const params = new URLSearchParams();
  params.set("n", "100");
  if (append && state.nextCursor) {
    params.set("last", state.nextCursor);
  }

  const result = await request(`/api/repositories?${params.toString()}`);
  const repos = Array.isArray(result.repositories) ? result.repositories : [];
  state.nextCursor = result.next || null;
  if (append) {
    state.repositories = [...new Set([...state.repositories, ...repos])];
  } else {
    state.repositories = repos;
  }
  applyRepoFilter();
  dom.loadMoreBtn.style.display = state.nextCursor ? "inline-block" : "none";
}

function renderTags(tags) {
  dom.tagTableBody.innerHTML = "";
  if (!tags || tags.length === 0) {
    dom.tagTableBody.innerHTML = `<tr><td colspan="5">No tags found.</td></tr>`;
    return;
  }

  for (const row of tags) {
    const tr = document.createElement("tr");
    if (row.error) {
      tr.innerHTML = `
        <td class="mono">${row.tag || "-"}</td>
        <td colspan="3" class="tag-error">${row.error}</td>
        <td class="action-col">-</td>
      `;
      dom.tagTableBody.appendChild(tr);
      continue;
    }

    const deleteButton = document.createElement("button");
    deleteButton.className = "danger-btn";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", () => deleteTag(row.tag));

    const actionTd = document.createElement("td");
    actionTd.className = "action-col";
    actionTd.appendChild(deleteButton);

    tr.innerHTML = `
      <td class="mono">${row.tag || "-"}</td>
      <td class="mono" title="${row.digest || ""}">${shortDigest(row.digest)}</td>
      <td>${formatBytes(row.size_bytes)}</td>
      <td>${formatDate(row.created_at)}</td>
    `;
    tr.appendChild(actionTd);
    dom.tagTableBody.appendChild(tr);
  }
}

async function selectRepository(repository) {
  state.selectedRepository = repository;
  dom.repoTitle.textContent = repository;
  setRepoMeta("Loading tags...");
  renderRepositoryList();
  await loadTags();
}

async function loadTags() {
  const repository = state.selectedRepository;
  if (!repository) {
    dom.repoTitle.textContent = "Select a repository";
    setRepoMeta("No repository selected.");
    renderTags([]);
    return;
  }
  const payload = await request(`/api/repositories/${encodeURIComponent(repository)}/tags`);
  const tags = Array.isArray(payload.tags) ? payload.tags : [];
  setRepoMeta(`Total tags: ${tags.length}`);
  renderTags(tags);
}

async function deleteTag(tag) {
  const repository = state.selectedRepository;
  if (!repository || !tag) {
    return;
  }
  const confirmed = window.confirm(`Delete ${repository}:${tag}?`);
  if (!confirmed) {
    return;
  }
  await request(`/api/repositories/${encodeURIComponent(repository)}/tags/${encodeURIComponent(tag)}`, {
    method: "DELETE",
  });
  await loadTags();
}

function setJobStatus(status) {
  const normalized = (status || "idle").toLowerCase();
  dom.jobStatusChip.className = "chip";
  dom.jobStatusChip.classList.add(normalized);
  dom.jobStatusChip.textContent = normalized.toUpperCase();
}

function renderJobLogs(logs = []) {
  dom.jobLogBox.textContent = logs.length > 0 ? logs.join("\n") : "No logs.";
  dom.jobLogBox.scrollTop = dom.jobLogBox.scrollHeight;
}

function stopJobPolling() {
  if (state.jobPollTimer) {
    clearInterval(state.jobPollTimer);
    state.jobPollTimer = null;
  }
}

async function onJobCompleted() {
  await Promise.allSettled([loadRepositories(), loadRecentJobs(), loadLocalImages()]);
  if (state.selectedRepository) {
    await loadTags();
  }
}

async function pollJob(jobId) {
  try {
    const job = await request(`/api/sync-jobs/${jobId}`);
    setJobStatus(job.status);
    renderJobLogs(job.logs || []);
    if (job.status === "success" || job.status === "failed") {
      stopJobPolling();
      await onJobCompleted();
    }
  } catch (error) {
    stopJobPolling();
    setJobStatus("failed");
    renderJobLogs([`Job polling failed: ${error.message}`]);
  }
}

function startJobPolling(jobId) {
  stopJobPolling();
  state.activeJobId = jobId;
  state.jobPollTimer = setInterval(() => {
    pollJob(jobId).catch((error) => {
      stopJobPolling();
      renderJobLogs([`Job polling error: ${error.message}`]);
    });
  }, 1800);
}

async function submitMirrorJob(event) {
  event.preventDefault();
  const sourceImage = dom.sourceImage.value.trim();
  const targetRepo = dom.targetRepo.value.trim();
  const targetTag = dom.targetTag.value.trim();
  if (!sourceImage) {
    window.alert("source image cannot be empty.");
    return;
  }

  dom.syncBtn.disabled = true;
  try {
    const body = {
      source_image: sourceImage,
      target_repository: targetRepo || null,
      target_tag: targetTag || null,
    };
    const created = await request("/api/sync-jobs", {
      method: "POST",
      body: JSON.stringify(body),
    });
    setJobStatus(created.status);
    renderJobLogs(created.logs || []);
    startJobPolling(created.id);
    await loadRecentJobs();
  } catch (error) {
    setJobStatus("failed");
    renderJobLogs([`Create job failed: ${error.message}`]);
  } finally {
    dom.syncBtn.disabled = false;
  }
}

function renderLocalImages() {
  dom.localImageList.innerHTML = "";
  if (state.localImages.length === 0) {
    dom.localImageList.innerHTML = `<li class="job-empty">No local images found.</li>`;
    updateLocalHint();
    return;
  }

  for (const image of state.localImages) {
    const li = document.createElement("li");
    li.className = "local-item";
    const checked = state.selectedLocalRefs.has(image.reference) ? "checked" : "";
    li.innerHTML = `
      <div class="local-row">
        <label class="local-ref">
          <input class="select-input" type="checkbox" data-ref="${image.reference}" ${checked} />
          ${image.reference}
        </label>
        <span class="local-meta">${image.size || "-"}</span>
      </div>
      <div class="local-meta">arch=${image.architecture || "-"} os=${image.os || "-"}</div>
    `;
    dom.localImageList.appendChild(li);
  }
  updateLocalHint();
}

async function loadLocalImages() {
  const result = await request("/api/local-images?limit=500");
  state.localImages = Array.isArray(result.images) ? result.images : [];
  state.detectedArch = result.detected_arch || state.detectedArch;

  const existingRefs = new Set(state.localImages.map((item) => item.reference));
  for (const ref of [...state.selectedLocalRefs]) {
    if (!existingRefs.has(ref)) {
      state.selectedLocalRefs.delete(ref);
    }
  }
  if (!dom.archValue.value.trim()) {
    dom.archValue.value = state.detectedArch;
  }
  renderLocalImages();
}

function collectSelectedLocalRefs() {
  const checkboxes = dom.localImageList.querySelectorAll("input[type='checkbox'][data-ref]");
  state.selectedLocalRefs.clear();
  for (const box of checkboxes) {
    if (box.checked) {
      state.selectedLocalRefs.add(box.dataset.ref);
    }
  }
}

async function submitLocalPushJob() {
  collectSelectedLocalRefs();
  if (state.selectedLocalRefs.size === 0) {
    window.alert("Please select at least one local image.");
    return;
  }

  const archMode = dom.archMode.value;
  const archValue = dom.archValue.value.trim();
  const prefixMode = dom.prefixMode.value;
  const prefixValue = dom.prefixValue.value.trim();
  if (archMode === "custom" && !archValue) {
    window.alert("Custom arch cannot be empty.");
    return;
  }
  if (prefixMode !== "none" && !prefixValue) {
    window.alert("Prefix value cannot be empty when prefix mode is add/remove.");
    return;
  }

  dom.pushLocalBtn.disabled = true;
  try {
    const created = await request("/api/local-push-jobs", {
      method: "POST",
      body: JSON.stringify({
        image_refs: [...state.selectedLocalRefs],
        arch_mode: archMode,
        arch_value: archValue,
        prefix_mode: prefixMode,
        prefix_value: prefixValue,
        cleanup_local_tag: Boolean(dom.cleanupLocalTag.checked),
        cleanup_registry_source_tag: Boolean(dom.cleanupRegistrySourceTag.checked),
      }),
    });
    setJobStatus(created.status);
    renderJobLogs(created.logs || []);
    startJobPolling(created.id);
    await loadRecentJobs();
  } catch (error) {
    setJobStatus("failed");
    renderJobLogs([`Create local push job failed: ${error.message}`]);
  } finally {
    dom.pushLocalBtn.disabled = false;
  }
}

function renderRecentJobs(jobs = []) {
  dom.jobList.innerHTML = "";
  if (jobs.length === 0) {
    dom.jobList.innerHTML = `<li class="job-empty">No jobs yet.</li>`;
    return;
  }

  for (const job of jobs) {
    const li = document.createElement("li");
    li.className = "job-item";
    li.innerHTML = `
      <div class="job-top">
        <span class="job-id">${job.id}</span>
        <span class="chip ${job.status}">${job.status}</span>
      </div>
      <div class="job-image">[${job.job_type || "mirror"}] ${job.source_image}</div>
      <div class="job-image">=> ${job.target_image} (${job.total_items || 1} item)</div>
      <div class="job-id">${formatDate(job.updated_at)}</div>
    `;
    li.addEventListener("click", async () => {
      const detail = await request(`/api/sync-jobs/${job.id}`);
      state.activeJobId = detail.id;
      setJobStatus(detail.status);
      renderJobLogs(detail.logs || []);
      if (detail.status === "running") {
        startJobPolling(detail.id);
      }
    });
    dom.jobList.appendChild(li);
  }
}

async function loadRecentJobs() {
  const result = await request("/api/sync-jobs?limit=20");
  const jobs = Array.isArray(result.jobs) ? result.jobs : [];
  renderRecentJobs(jobs);
}

function bindEvents() {
  dom.repoSearch.addEventListener("input", applyRepoFilter);
  dom.loadMoreBtn.addEventListener("click", async () => {
    try {
      await loadRepositories({ append: true });
    } catch (error) {
      window.alert(`Load more repositories failed: ${error.message}`);
    }
  });
  dom.refreshReposBtn.addEventListener("click", async () => {
    try {
      await loadRepositories();
    } catch (error) {
      window.alert(`Refresh repositories failed: ${error.message}`);
    }
  });
  dom.refreshTagsBtn.addEventListener("click", async () => {
    try {
      await loadTags();
    } catch (error) {
      window.alert(`Refresh tags failed: ${error.message}`);
    }
  });
  dom.refreshJobsBtn.addEventListener("click", async () => {
    try {
      await loadRecentJobs();
    } catch (error) {
      window.alert(`Refresh jobs failed: ${error.message}`);
    }
  });
  dom.syncForm.addEventListener("submit", submitMirrorJob);
  dom.refreshLocalBtn.addEventListener("click", async () => {
    try {
      await loadLocalImages();
    } catch (error) {
      window.alert(`Load local images failed: ${error.message}`);
    }
  });
  dom.selectAllLocalBtn.addEventListener("click", () => {
    for (const item of state.localImages) {
      state.selectedLocalRefs.add(item.reference);
    }
    renderLocalImages();
  });
  dom.clearLocalBtn.addEventListener("click", () => {
    state.selectedLocalRefs.clear();
    renderLocalImages();
  });
  dom.pushLocalBtn.addEventListener("click", submitLocalPushJob);
  dom.localImageList.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) {
      return;
    }
    const ref = target.dataset.ref;
    if (!ref) {
      return;
    }
    if (target.checked) {
      state.selectedLocalRefs.add(ref);
    } else {
      state.selectedLocalRefs.delete(ref);
    }
    updateLocalHint();
  });
}

async function bootstrap() {
  bindEvents();
  setJobStatus("idle");
  await Promise.all([
    refreshHealth(),
    loadRepositories(),
    loadRecentJobs(),
    loadLocalImages(),
  ]);
  if (state.repositories.length > 0) {
    await selectRepository(state.repositories[0]);
  } else {
    renderTags([]);
  }
  setInterval(() => {
    refreshHealth().catch(() => {
      // Keep current status if periodic check fails.
    });
  }, 10000);
}

bootstrap().catch((error) => {
  window.alert(`Bootstrap failed: ${error.message}`);
});
