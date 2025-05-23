/** @type {import('tailwindcss').Config} */
const colors = require("tailwindcss/colors");

module.exports = {
    content: ["app/**/templates/**/*.html"],
    darkMode: "selector",
    theme: {
        extend: {
            colors: {
                surface: colors.zinc,
                secondary: colors.slate,
                primary: colors.blue,
                accent: colors.sky,
                alert: colors.rose,
            },
            fontFamily: {
                sans: ["Outfit", '"Inter var"', "Inter", "sans-serif"],
                mono: ['"Fira Mono"', '"JetBrains Mono"', "monospace"],
            },
        },
    },
    plugins: [
        require("@tailwindcss/typography"),
        require("@tailwindcss/forms"),
    ],
};
