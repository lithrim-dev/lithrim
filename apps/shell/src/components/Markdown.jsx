/* Markdown.jsx — render streamed assistant text as markdown. remark-gfm adds tables,
   strikethrough, task lists, and autolinks. There is deliberately NO rehype-raw: any
   raw HTML in model output is rendered as inert text, never live DOM, so the chat
   surface is XSS-safe by construction. The non-vacuous regression guard for that
   posture lives in Markdown.test.jsx — do not add rehype-raw without revisiting it.
   Links are forced into a new tab as untrusted. */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const COMPONENTS = {
  // strip react-markdown's `node` prop and harden every rendered link.
  a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer nofollow" />,
};

export function Markdown({ children }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {children || ""}
      </ReactMarkdown>
    </div>
  );
}
