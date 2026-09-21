import { describe, expect, it } from "vitest";
import headerSource from "./Header.tsx?raw";

describe("Header demo calls to action", () => {
  it("keeps desktop and mobile demo calls on the published demo route", () => {
    expect(headerSource.match(/href="\/demo"/g)).toHaveLength(2);
  });
});
