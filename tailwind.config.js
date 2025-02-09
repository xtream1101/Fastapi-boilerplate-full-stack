/** @type {import('tailwindcss').Config} */
module.exports = {
    content: ["app/**/templates/**/*.html"],
    darkMode: "selector",
    theme: {
        extend: {
            colors: {
                primary: {
                    50: "#fafaf9",
                    100: "#f5f5f4",
                    200: "#e7e5e4",
                    300: "#d6d3d1",
                    400: "#a8a29e",
                    500: "#78716c",
                    600: "#57534e",
                    700: "#44403c",
                    800: "#292524",
                    900: "#1c1917",
                },
                gray: {
                    50: "#fafaf9",
                    100: "#f5f5f4",
                    200: "#e7e5e4",
                    300: "#d6d3d1",
                    400: "#a8a29e",
                    500: "#78716c",
                    600: "#57534e",
                    700: "#44403c",
                    800: "#292524",
                    900: "#1c1917",
                },
                accent: {
                    light: "#f43f5e",
                    DEFAULT: "#e11d48",
                    dark: "#be123c",
                },
                fun: {
                    yellow: "#fbbf24",
                    green: "#34d399",
                    blue: "#38bdf8",
                    pink: "#f472b6",
                    orange: "#fb923c",
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
