function submitAssociation(teamId, networkId) {
  const form = document.getElementById(`associateForm${teamId}`);
  const networkInput = document.getElementById(`networkIdInput${teamId}`);
  networkInput.value = networkId;
  form.submit();
}

function submitAssociationRemoval(teamId) {
  const form = document.getElementById(`deleteAssocForm${teamId}`);
  form.submit();
}

function submitZerotierRemoval(networkId) {
  const form = document.getElementById(`deleteZerotierForm${networkId}`);
  form.submit();
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".hikari-zerotier-associate").forEach((button) => {
    button.addEventListener("click", () => {
      submitAssociation(button.dataset.teamId, button.dataset.networkId);
    });
  });

  document.querySelectorAll(".hikari-zerotier-delete-association").forEach((button) => {
    button.addEventListener("click", () => {
      submitAssociationRemoval(button.dataset.teamId);
    });
  });

  document.querySelectorAll(".hikari-zerotier-delete").forEach((button) => {
    button.addEventListener("click", () => {
      submitZerotierRemoval(button.dataset.networkId);
    });
  });
});
