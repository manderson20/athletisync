document.body.addEventListener("htmx:responseError", () => {
  window.alert("AthletiSync request failed. Check the server logs for details.");
});
