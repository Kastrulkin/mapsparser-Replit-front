import { describe, expect, it } from "vitest";
import { videoArticles } from "./videoArticles";

const channelVideoIds = [
  "3QXJ9i1AOkc",
  "O10xMNs-HDw",
  "yE5yvdT_IhY",
  "HZdbh_NXbP4",
  "r77B57K1et4",
  "-yr91HhX0GU",
  "1LyGJRVcmoY",
  "s0mECDv_65o",
];

describe("videoArticles", () => {
  it("publishes one complete article for every video on the channel", () => {
    expect(videoArticles).toHaveLength(channelVideoIds.length);
    expect(videoArticles.map((article) => article.video?.youtubeId)).toEqual(
      expect.arrayContaining(channelVideoIds),
    );

    for (const article of videoArticles) {
      expect(article.draft).toBe(false);
      expect(article.slug).toBeTruthy();
      expect(article.excerpt.length).toBeGreaterThan(80);
      expect(article.body.length).toBeGreaterThanOrEqual(6);
      expect(article.video?.title).toBeTruthy();
    }
  });

  it("does not reuse slugs or videos", () => {
    const slugs = videoArticles.map((article) => article.slug);
    const videoIds = videoArticles.map((article) => article.video?.youtubeId);

    expect(new Set(slugs).size).toBe(slugs.length);
    expect(new Set(videoIds).size).toBe(videoIds.length);
  });
});
