import useCopyToClipboard from "./scripts/useCopyToClipboard.js";

document.addEventListener("DOMContentLoaded", (event) => {
    // Initialize remaining modules
    const copyToClipboard = useCopyToClipboard();

    // Setup remaining modules
    copyToClipboard.setup();
});
