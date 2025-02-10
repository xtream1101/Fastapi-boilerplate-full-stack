/** @type {import('tailwindcss').Config} */
module.exports = {
    content: ["app/**/templates/**/*.html"],
    darkMode: "selector",
    theme: {
        extend: {
            colors: {
                primary: {
                    50: "#f8f9fa",
                    100: "#f1f3f5",
                    200: "#e9ecef",
                    300: "#dee2e6",
                    400: "#ced4da",
                    500: "#adb5bd",
                    600: "#6c757d",
                    700: "#495057",
                    800: "#343a40",
                    900: "#1a1a1a",
                },
                gray: {
                    50: "#f8f9fa",
                    100: "#f1f3f5",
                    200: "#e9ecef",
                    300: "#dee2e6",
                    400: "#ced4da",
                    500: "#adb5bd",
                    600: "#6c757d",
                    700: "#495057",
                    800: "#343a40",
                    900: "#1a1a1a",
                },
                accent: {
                    light: "#4dabf7",
                    DEFAULT: "#228be6",
                    dark: "#1971c2",
                },
                fun: {
                    yellow: "#ffd43b",
                    green: "#20c997",
                    blue: "#339af0",
                    pink: "#e64980",
                    orange: "#fd7e14",
                },
            },
            fontFamily: {
                sans: ["Outfit", '"Inter var"', "Inter", "sans-serif"],
                mono: ['"Fira Mono"', '"JetBrains Mono"', "monospace"],
            },
            typography: ({ theme }) => ({
                DEFAULT: {
                    css: {
                        pre: null,
                        code: null,
                        "code::before": null,
                        "code::after": null,
                        "pre code": null,
                        "pre code::before": null,
                        "pre code::after": null,
                    },
                },
            }),
        },
    },
    plugins: [require("@tailwindcss/typography")],
};
