/**
 * Minimal dashboard client for the defect tracker API.
 * The page is served by the same FastAPI application, so relative URLs work.
 */
const API = "";

const state = {
  page: 1,
  pageSize: 10,
  severity: "",
  status: "",
  sortBy: "created_at",
  order: "desc",
  pages: 0,
};

const $ = (id) => document.getElementById(id);

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (response.status === 204) return null;

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body?.error?.details?.map((d) => `${d.field}: ${d.message}`).join(", ");
    throw new Error(body?.error?.message ? `${body.error.message}${detail ? ` (${detail})` : ""}` : `HTTP ${response.status}`);
  }
  return body;
}

function setMessage(element, text, ok = false) {
  element.textContent = text;
  element.className = `message ${ok ? "ok" : "error"}`;
}

function badgeClass(value) {
  return `badge ${String(value).toLowerCase().replace(" ", "-")}`;
}

async function loadStats() {
  try {
    const stats = await apiFetch("/issues/stats");
    $("stat-total").textContent = stats.total;
    $("stat-open").textContent = stats.by_status["Open"] ?? 0;
    $("stat-in-progress").textContent = stats.by_status["In Progress"] ?? 0;
    $("stat-closed").textContent = stats.by_status["Closed"] ?? 0;
    $("stat-critical").textContent = stats.by_severity["Critical"] ?? 0;
    $("severity-buckets").textContent = Object.entries(stats.by_severity)
      .map(([key, value]) => `${key}: ${value}`)
      .join("  |  ");
  } catch (error) {
    $("severity-buckets").textContent = `Statistics unavailable: ${error.message}`;
  }
}

async function loadIssues() {
  const params = new URLSearchParams({
    page: state.page,
    page_size: state.pageSize,
    sort_by: state.sortBy,
    order: state.order,
  });
  if (state.severity) params.set("severity", state.severity);
  if (state.status) params.set("status", state.status);

  const body = await apiFetch(`/issues?${params.toString()}`);
  state.pages = body.pages;

  const tbody = $("issues-body");
  tbody.innerHTML = "";

  if (body.items.length === 0) {
    setMessage($("table-message"), "No defects match the current filters.");
  } else {
    setMessage($("table-message"), `${body.total} defect(s) in total.`, true);
  }

  for (const issue of body.items) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${issue.id}</td>
      <td>${escapeHtml(issue.title)}</td>
      <td><span class="${badgeClass(issue.severity)}">${issue.severity}</span></td>
      <td>${issue.status}</td>
      <td>${issue.category}</td>
      <td>${issue.environment}</td>
      <td>${new Date(issue.updated_at).toISOString().replace("T", " ").slice(0, 19)}</td>
      <td class="actions"></td>`;
    const actions = row.querySelector(".actions");

    for (const nextStatus of ["In Progress", "Closed"]) {
      if (issue.status === nextStatus) continue;
      const button = document.createElement("button");
      button.className = "secondary";
      button.textContent = nextStatus;
      button.onclick = async () => {
        try {
          await apiFetch(`/issues/${issue.id}`, {
            method: "PATCH",
            body: JSON.stringify({ status: nextStatus }),
          });
          await refresh();
        } catch (error) {
          setMessage($("table-message"), error.message);
        }
      };
      actions.appendChild(button);
    }

    const deleteButton = document.createElement("button");
    deleteButton.className = "danger";
    deleteButton.textContent = "Delete";
    deleteButton.onclick = async () => {
      try {
        await apiFetch(`/issues/${issue.id}`, { method: "DELETE" });
        await refresh();
      } catch (error) {
        setMessage($("table-message"), error.message);
      }
    };
    actions.appendChild(deleteButton);

    tbody.appendChild(row);
  }

  $("page-info").textContent = `Page ${body.page} of ${Math.max(state.pages, 1)}`;
  $("prev-page").disabled = state.page <= 1;
  $("next-page").disabled = state.pages === 0 || state.page >= state.pages;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]
  ));
}

async function refresh() {
  await Promise.all([loadIssues(), loadStats()]);
}

$("issue-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target).entries());
  if (!data.description) delete data.description;

  try {
    const created = await apiFetch("/issues", { method: "POST", body: JSON.stringify(data) });
    setMessage($("form-message"), `Created defect #${created.id}.`, true);
    state.page = 1;
    await refresh();
  } catch (error) {
    setMessage($("form-message"), error.message);
  }
});

$("filter-severity").addEventListener("change", (event) => {
  state.severity = event.target.value;
  state.page = 1;
  loadIssues().catch((error) => setMessage($("table-message"), error.message));
});

$("filter-status").addEventListener("change", (event) => {
  state.status = event.target.value;
  state.page = 1;
  loadIssues().catch((error) => setMessage($("table-message"), error.message));
});

$("filter-sort").addEventListener("change", (event) => {
  const [sortBy, order] = event.target.value.split(":");
  state.sortBy = sortBy;
  state.order = order;
  state.page = 1;
  loadIssues().catch((error) => setMessage($("table-message"), error.message));
});

$("filter-page-size").addEventListener("change", (event) => {
  state.pageSize = Number(event.target.value);
  state.page = 1;
  loadIssues().catch((error) => setMessage($("table-message"), error.message));
});

$("prev-page").addEventListener("click", () => {
  if (state.page > 1) {
    state.page -= 1;
    loadIssues().catch((error) => setMessage($("table-message"), error.message));
  }
});

$("next-page").addEventListener("click", () => {
  if (state.page < state.pages) {
    state.page += 1;
    loadIssues().catch((error) => setMessage($("table-message"), error.message));
  }
});

$("refresh").addEventListener("click", () => refresh());

refresh().catch((error) => setMessage($("table-message"), error.message));
