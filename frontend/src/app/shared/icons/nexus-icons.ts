/**
 * SPEC-015 (D2): icones de traco fino no estilo do Gemini. Cada icone e uma lista de
 * formas SVG (viewBox 24x24) desenhadas pelo `nexus-icon`; nada vem de fora.
 */
export interface IconShapes {
  readonly paths: readonly string[];
  readonly rects?: readonly { x: number; y: number; w: number; h: number; r: number }[];
  readonly circles?: readonly { cx: number; cy: number; r: number }[];
}

export const NEXUS_ICONS = {
  newChat: {
    paths: ["M12 3.5a8.5 8.5 0 1 0 8.5 8.5", "M18 4.5a2.12 2.12 0 0 1 3 3L13.5 15l-4 1 1-4z"]
  },
  assistants: {
    paths: [],
    rects: [
      { x: 3.5, y: 3.5, w: 7, h: 7, r: 2 },
      { x: 13.5, y: 3.5, w: 7, h: 7, r: 2 },
      { x: 3.5, y: 13.5, w: 7, h: 7, r: 2 },
      { x: 13.5, y: 13.5, w: 7, h: 7, r: 2 }
    ]
  },
  recent: { paths: ["M12 7v5l3.2 2"], circles: [{ cx: 12, cy: 12, r: 8.75 }] },
  conversation: { paths: ["M7.9 20A9 9 0 1 0 4 16.1L2.5 21.5z"] },
  trash: {
    paths: [
      "M3.5 6h17",
      "M18.5 6v13.5a2 2 0 0 1-2 2h-9a2 2 0 0 1-2-2V6",
      "M8.5 6V4.5a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2V6"
    ]
  },
  settings: {
    paths: [
      "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"
    ],
    circles: [{ cx: 12, cy: 12, r: 3 }]
  },
  logout: {
    paths: ["M9 21H5.5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2H9", "m16 17 5-5-5-5", "M21 12H9"]
  },
  panelOpen: {
    paths: ["M9.5 3.5v17", "m13.5 9.5 2.5 2.5-2.5 2.5"],
    rects: [{ x: 3.5, y: 3.5, w: 17, h: 17, r: 3.5 }]
  },
  panelClose: {
    paths: ["M9.5 3.5v17"],
    rects: [{ x: 3.5, y: 3.5, w: 17, h: 17, r: 3.5 }]
  },
  menu: { paths: ["M4 6.5h16", "M4 12h16", "M4 17.5h16"] },
  plus: { paths: ["M12 5v14", "M5 12h14"] },
  chevronDown: { paths: ["m6 9 6 6 6-6"] },
  chevronUp: { paths: ["m18 15-6-6-6 6"] },
  documents: {
    paths: [
      "M14.5 2.5H6.5a2 2 0 0 0-2 2v15a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7.5z",
      "M14 2.5v3.5a2 2 0 0 0 2 2h3.5",
      "M15.5 13h-7",
      "M15.5 17h-7",
      "M10.5 9h-2"
    ]
  },
  audit: {
    paths: ["m9 11 3 3L21.5 4.5", "M20.5 12v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2V5.5a2 2 0 0 1 2-2H16"]
  },
  archived: {
    paths: ["M4.5 8.5v10.5a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V8.5", "M10 12.5h4"],
    rects: [{ x: 2.5, y: 3.5, w: 19, h: 5, r: 1.5 }]
  },
  feedback: {
    paths: [
      "M7 10v11.5",
      "M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"
    ]
  },
  usage: { paths: ["M3.5 3.5V19a2 2 0 0 0 2 2h15", "M18 17V9", "M13 17V5", "M8 17v-3"] },
  llmCredentials: {
    paths: [
      "M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"
    ],
    circles: [{ cx: 16.5, cy: 7.5, r: 1 }]
  }
} as const satisfies Record<string, IconShapes>;

export type NexusIconName = keyof typeof NEXUS_ICONS | "logo";
