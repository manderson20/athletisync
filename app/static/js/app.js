document.body.addEventListener("htmx:responseError", () => {
  window.alert("AthletiSync request failed. Check the server logs for details.");
});

document.body.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-activity-select]");
  if (!trigger) {
    return;
  }

  const activityId = trigger.getAttribute("data-activity-select");
  const rows = document.querySelectorAll("#activity-list .grouped-row");
  rows.forEach((row) => {
    row.classList.toggle("is-selected", row.getAttribute("data-activity-id") === activityId);
  });
});
