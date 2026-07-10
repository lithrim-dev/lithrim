/* Markdown.test.jsx — D1 + A1. Proves the chat markdown renderer (1) formats real
   markdown and (2) renders raw HTML in model output as INERT text, never live DOM.

   The sanitization assertion is deliberately NON-VACUOUS: react-markdown@9 without
   rehype-raw emits no HTML element anyway, so a bare "no <script> node" check would
   pass trivially. So one message MIXES **bold** with a <script> and an <img onerror>
   payload, and we assert BOTH that the markdown rendered AND that no <script>/<img>
   element (and no onerror handler) exists. If anyone ever adds rehype-raw, the payload
   half fails — this is the regression guard for the "no rehype-raw" posture. */
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Markdown } from "./Markdown.jsx";

describe("Markdown — chat assistant rendering (D1/A1)", () => {
  it("renders bold, lists, and fenced code as real markdown nodes", () => {
    const { container } = render(
      <Markdown>{"Here is **bold** text\n\n- one\n- two\n\n```\ncode block\n```"}</Markdown>,
    );
    expect(container.querySelector("strong")?.textContent).toBe("bold");
    expect(container.querySelectorAll("li")).toHaveLength(2);
    const code = container.querySelector("pre code");
    expect(code).toBeTruthy();
    expect(code?.textContent).toContain("code block");
  });

  it("renders a GFM table (remark-gfm is wired)", () => {
    const { container } = render(<Markdown>{"| a | b |\n| - | - |\n| 1 | 2 |"}</Markdown>);
    expect(container.querySelector("table")).toBeTruthy();
    expect(container.querySelectorAll("td")).toHaveLength(2);
  });

  it("renders raw HTML payloads as INERT text, not live DOM (no rehype-raw)", () => {
    const mixed =
      "Real **markdown** survives.\n\n" +
      "<script>window.__xss = 1</script>\n\n" +
      '<img src=x onerror="window.__xss = 1">';
    const { container } = render(<Markdown>{mixed}</Markdown>);

    // (1) non-vacuous: the markdown actually rendered (this isn't an empty/blocked render)
    expect(container.querySelector("strong")?.textContent).toBe("markdown");

    // (2) the payloads are inert — NO live element was created from the raw HTML
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("[onerror]")).toBeNull();
    // belt-and-suspenders: the side effect never fired
    expect(window.__xss).toBeUndefined();
  });

  it("hardens links: target=_blank rel=noopener noreferrer nofollow", () => {
    const { container } = render(<Markdown>{"[lithrim](https://example.com)"}</Markdown>);
    const a = container.querySelector("a");
    expect(a?.getAttribute("target")).toBe("_blank");
    expect(a?.getAttribute("rel")).toBe("noopener noreferrer nofollow");
  });
});
