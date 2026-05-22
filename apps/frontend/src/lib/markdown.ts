import MarkdownIt from 'markdown-it';

export const safeMarkdown = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
});
