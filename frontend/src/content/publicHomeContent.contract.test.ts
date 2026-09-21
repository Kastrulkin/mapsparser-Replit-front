import { describe, expect, it } from "vitest";
import indexSource from "../pages/Index.tsx?raw";
import { publicHomeContent } from "./publicHomeContent";

describe("public homepage heading", () => {
  it("shares the already-published H1 with the JavaScript homepage", () => {
    expect(publicHomeContent.heading).toBe("Не держите весь бизнес в голове");
    expect(indexSource).toContain("title: publicHomeContent.heading");
  });
});
