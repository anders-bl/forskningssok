// Entry for frontend/vendor/tiptap.js. Eksponerer akkurat det index.html trenger som ett
// globalt objekt; ingen ESM i nettleseren, ingen CDN (privat forskningsflate bak auth).
import { Editor, Node, mergeAttributes } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { Markdown } from "tiptap-markdown";
window.TipTap = { Editor, Node, mergeAttributes, StarterKit, Placeholder, Markdown };
