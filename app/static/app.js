import useCopyToClipboard from "./scripts/useCopyToClipboard.js";
import useDateFormatter from "./scripts/useDateFormatter.js";

document.addEventListener("DOMContentLoaded", (event) => {
    // Initialize remaining modules
    const copyToClipboard = useCopyToClipboard();
    const dateFormatter = useDateFormatter();

    // Setup remaining modules
    copyToClipboard.setup();
    dateFormatter.format();
});
