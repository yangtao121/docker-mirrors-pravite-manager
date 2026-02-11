const state = {
  repositories: [],
  filteredRepositories: [],
  nextCursor: null,
  nonEmptyOnly: true,
  selectedRepository: null,
  activeJobId: null,
  jobPollTimer: null,
  localImages: [],
  selectedLocalRefs: new Set(),
  selectedRemoteRepos: new Set(),
  detectedArch: "unknown",
};

const dom = {
  healthDot: document.querySelector("#healthDot"),
  healthText: document.querySelector("#healthText"),
  repoSearch: document.querySelector("#repoSearch"),
  repoList: document.querySelector("#repoList"),
  loadMoreBtn: document.querySelector("#loadMoreBtn"),
  refreshReposBtn: document.querySelector("#refreshReposBtn"),
  selectAllRemoteBtn: document.querySelector("#selectAllRemoteBtn"),
  clearRemoteBtn: document.querySelector("#clearRemoteBtn"),
  remotePrefixMode: document.querySelector("#remotePrefixMode"),
  remotePrefixValue: document.querySelector("#remotePrefixValue"),
  cleanupRemoteSourceTag: document.querySelector("#cleanupRemoteSourceTag"),
  runRemotePrefixBtn: document.querySelector("#runRemotePrefixBtn"),
  runRemoteDeleteBtn: document.querySelector("#runRemoteDeleteBtn"),
  remoteHint: document.querySelector("#remoteHint"),
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
  dom.localHint.textContent = `检测到架构：${state.detectedArch} ｜ 已选择：${selected} ｜ 本地镜像总数：${state.localImages.length}`;
}

async function refreshHealth() {
  try {
    const result = await request("/api/health");
    state.detectedArch = result.detected_arch || state.detectedArch;
    updateLocalHint();
    const message = result.registry_healthy
      ? `仓库在线（${result.registry_push_host}）`
      : `仓库不可达（${result.registry_push_host}）`;
    setHealth(Boolean(result.registry_healthy), message);
  } catch (error) {
    setHealth(false, `健康检查失败：${error.message}`);
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
    dom.repoList.innerHTML = `<li class="repo-empty">未找到可用仓库（已自动过滤空仓库）。</li>`;
    updateRemoteHint();
    return;
  }
  for (const repo of state.filteredRepositories) {
    const item = document.createElement("li");
    item.className = `repo-item${repo === state.selectedRepository ? " active" : ""}`;
    const checked = state.selectedRemoteRepos.has(repo) ? "checked" : "";
    item.innerHTML = `
      <div class="repo-row">
        <input class="select-input" type="checkbox" data-repo="${repo}" ${checked} />
        <span class="repo-name">${repo}</span>
      </div>
    `;
    const repoNameEl = item.querySelector(".repo-name");
    if (repoNameEl) {
      repoNameEl.addEventListener("click", () => selectRepository(repo));
    }
    dom.repoList.appendChild(item);
  }
  updateRemoteHint();
}

function setRepoMeta(message) {
  dom.repoMeta.textContent = message;
}

function updateRemoteHint() {
  dom.remoteHint.textContent = `已选仓库：${state.selectedRemoteRepos.size}`;
}

async function loadRepositories({ append = false } = {}) {
  const params = new URLSearchParams();
  params.set("n", "100");
  if (state.nonEmptyOnly) {
    params.set("non_empty_only", "true");
  }
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
  const existingRepos = new Set(state.repositories);
  for (const repo of [...state.selectedRemoteRepos]) {
    if (!existingRepos.has(repo)) {
      state.selectedRemoteRepos.delete(repo);
    }
  }
  applyRepoFilter();
  dom.loadMoreBtn.style.display = state.nextCursor ? "inline-block" : "none";
  updateRemoteHint();
}

function renderTags(tags) {
  dom.tagTableBody.innerHTML = "";
  if (!tags || tags.length === 0) {
    dom.tagTableBody.innerHTML = `<tr><td colspan="5">未找到标签。</td></tr>`;
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
    deleteButton.textContent = "删除";
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
  setRepoMeta("正在加载标签...");
  renderRepositoryList();
  await loadTags();
}

async function loadTags() {
  const repository = state.selectedRepository;
  if (!repository) {
    dom.repoTitle.textContent = "请选择一个仓库";
    setRepoMeta("尚未选择仓库。");
    renderTags([]);
    return;
  }
  const payload = await request(`/api/repositories/${encodeURIComponent(repository)}/tags`);
  const tags = Array.isArray(payload.tags) ? payload.tags : [];
  setRepoMeta(`标签总数：${tags.length}`);
  renderTags(tags);
}

async function deleteTag(tag) {
  const repository = state.selectedRepository;
  if (!repository || !tag) {
    return;
  }
  const confirmed = window.confirm(`确认删除 ${repository}:${tag} 吗？`);
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
  const statusText = {
    idle: "空闲",
    running: "运行中",
    success: "成功",
    failed: "失败",
  };
  dom.jobStatusChip.textContent = statusText[normalized] || normalized;
}

function renderJobLogs(logs = []) {
  dom.jobLogBox.textContent = logs.length > 0 ? logs.join("\n") : "暂无日志。";
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
    renderJobLogs([`任务状态轮询失败：${error.message}`]);
  }
}

function startJobPolling(jobId) {
  stopJobPolling();
  state.activeJobId = jobId;
  state.jobPollTimer = setInterval(() => {
    pollJob(jobId).catch((error) => {
      stopJobPolling();
      renderJobLogs([`任务轮询异常：${error.message}`]);
    });
  }, 1800);
}

async function submitMirrorJob(event) {
  event.preventDefault();
  const sourceImage = dom.sourceImage.value.trim();
  const targetRepo = dom.targetRepo.value.trim();
  const targetTag = dom.targetTag.value.trim();
  if (!sourceImage) {
    window.alert("源镜像不能为空。");
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
    renderJobLogs([`创建任务失败：${error.message}`]);
  } finally {
    dom.syncBtn.disabled = false;
  }
}

function renderLocalImages() {
  dom.localImageList.innerHTML = "";
  if (state.localImages.length === 0) {
    dom.localImageList.innerHTML = `<li class="job-empty">未找到本地镜像。</li>`;
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
    window.alert("请至少选择一个本地镜像。");
    return;
  }

  const archMode = dom.archMode.value;
  const archValue = dom.archValue.value.trim();
  const prefixMode = dom.prefixMode.value;
  const prefixValue = dom.prefixValue.value.trim();
  if (archMode === "custom" && !archValue) {
    window.alert("自定义架构值不能为空。");
    return;
  }
  if (prefixMode !== "none" && !prefixValue) {
    window.alert("当前选择了前缀加减模式，前缀值不能为空。");
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
    renderJobLogs([`创建本地批量上传任务失败：${error.message}`]);
  } finally {
    dom.pushLocalBtn.disabled = false;
  }
}

async function submitRemotePrefixJob() {
  if (state.selectedRemoteRepos.size === 0) {
    window.alert("请至少选择一个远程仓库。");
    return;
  }
  const prefixMode = dom.remotePrefixMode.value;
  const prefixValue = dom.remotePrefixValue.value.trim();
  if (!prefixValue) {
    window.alert("远程前缀值不能为空。");
    return;
  }

  const confirmed = window.confirm(
    `确认对 ${state.selectedRemoteRepos.size} 个仓库执行前缀重命名吗？`,
  );
  if (!confirmed) {
    return;
  }

  dom.runRemotePrefixBtn.disabled = true;
  try {
    const created = await request("/api/remote-prefix-jobs", {
      method: "POST",
      body: JSON.stringify({
        repositories: [...state.selectedRemoteRepos],
        prefix_mode: prefixMode,
        prefix_value: prefixValue,
        cleanup_source_tag: Boolean(dom.cleanupRemoteSourceTag.checked),
      }),
    });
    setJobStatus(created.status);
    renderJobLogs(created.logs || []);
    startJobPolling(created.id);
    await loadRecentJobs();
  } catch (error) {
    setJobStatus("failed");
    renderJobLogs([`创建远程批量重命名任务失败：${error.message}`]);
  } finally {
    dom.runRemotePrefixBtn.disabled = false;
  }
}

async function submitRepositoryDeleteJob() {
  if (state.selectedRemoteRepos.size === 0) {
    window.alert("请至少选择一个远程仓库。");
    return;
  }
  const confirmed = window.confirm(
    `确认删除已选中的 ${state.selectedRemoteRepos.size} 个仓库吗？\n此操作会删除仓库下所有标签。`,
  );
  if (!confirmed) {
    return;
  }

  dom.runRemoteDeleteBtn.disabled = true;
  try {
    const created = await request("/api/repository-delete-jobs", {
      method: "POST",
      body: JSON.stringify({
        repositories: [...state.selectedRemoteRepos],
      }),
    });
    setJobStatus(created.status);
    renderJobLogs(created.logs || []);
    startJobPolling(created.id);
    await loadRecentJobs();
  } catch (error) {
    setJobStatus("failed");
    renderJobLogs([`创建仓库删除任务失败：${error.message}`]);
  } finally {
    dom.runRemoteDeleteBtn.disabled = false;
  }
}

function renderRecentJobs(jobs = []) {
  dom.jobList.innerHTML = "";
  if (jobs.length === 0) {
    dom.jobList.innerHTML = `<li class="job-empty">暂无任务记录。</li>`;
    return;
  }

  for (const job of jobs) {
    const li = document.createElement("li");
    li.className = "job-item";
    li.innerHTML = `
      <div class="job-top">
        <span class="job-id">${job.id}</span>
        <span class="chip ${job.status}">${({ running: "运行中", success: "成功", failed: "失败", idle: "空闲" }[job.status] || job.status)}</span>
      </div>
      <div class="job-image">[${job.job_type === "local-push" ? "本地批量上传" : job.job_type === "remote-prefix" ? "远程前缀重命名" : job.job_type === "repo-delete" ? "仓库批量删除" : "远程同步"}] ${job.source_image}</div>
      <div class="job-image">=> ${job.target_image}（${job.total_items || 1} 项）</div>
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
      window.alert(`加载更多仓库失败：${error.message}`);
    }
  });
  dom.refreshReposBtn.addEventListener("click", async () => {
    try {
      await loadRepositories();
    } catch (error) {
      window.alert(`刷新仓库失败：${error.message}`);
    }
  });
  dom.selectAllRemoteBtn.addEventListener("click", () => {
    for (const repo of state.filteredRepositories) {
      state.selectedRemoteRepos.add(repo);
    }
    renderRepositoryList();
  });
  dom.clearRemoteBtn.addEventListener("click", () => {
    state.selectedRemoteRepos.clear();
    renderRepositoryList();
  });
  dom.runRemotePrefixBtn.addEventListener("click", submitRemotePrefixJob);
  dom.runRemoteDeleteBtn.addEventListener("click", submitRepositoryDeleteJob);
  dom.refreshTagsBtn.addEventListener("click", async () => {
    try {
      await loadTags();
    } catch (error) {
      window.alert(`刷新标签失败：${error.message}`);
    }
  });
  dom.refreshJobsBtn.addEventListener("click", async () => {
    try {
      await loadRecentJobs();
    } catch (error) {
      window.alert(`刷新任务失败：${error.message}`);
    }
  });
  dom.syncForm.addEventListener("submit", submitMirrorJob);
  dom.refreshLocalBtn.addEventListener("click", async () => {
    try {
      await loadLocalImages();
    } catch (error) {
      window.alert(`加载本地镜像失败：${error.message}`);
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
  dom.repoList.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) {
      return;
    }
    const repo = target.dataset.repo;
    if (!repo) {
      return;
    }
    if (target.checked) {
      state.selectedRemoteRepos.add(repo);
    } else {
      state.selectedRemoteRepos.delete(repo);
    }
    updateRemoteHint();
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
  window.alert(`页面初始化失败：${error.message}`);
});
