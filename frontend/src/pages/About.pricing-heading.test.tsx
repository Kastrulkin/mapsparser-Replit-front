import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { LanguageProvider } from "@/i18n/LanguageContext";
import About from "./About";

const renderAbout = (pricingOnly: boolean) => render(
  <MemoryRouter>
    <LanguageProvider>
      <About pricingOnly={pricingOnly} />
    </LanguageProvider>
  </MemoryRouter>,
);

describe("About pricing heading hierarchy", () => {
  afterEach(() => {
    window.localStorage.clear();
    window.history.replaceState({}, '', '/');
  });

  it("keeps the About pricing heading subordinate and gives /pricing its page H1", async () => {
    window.localStorage.setItem("language", "en");
    const about = renderAbout(false);
    await screen.findByRole("button", { name: "Start" });
    expect(about.container.querySelector("#pricing h1")).toBeNull();
    expect(about.container.querySelector("#pricing h2")).not.toBeNull();

    about.unmount();
    const pricing = renderAbout(true);
    await screen.findByRole("button", { name: "Start" });
    expect(pricing.container.querySelector("#pricing h1")?.textContent).toBe("Тарифы LocalOS");
    expect(pricing.container.querySelector("#pricing h2")).toBeNull();
  });

  it("shows Armenian pricing copy on a shared /pricing language link", async () => {
    window.localStorage.setItem("language", "ru");
    window.history.replaceState({}, '', '/pricing?lang=hy');
    renderAbout(true);

    expect(await screen.findByRole("heading", { level: 1, name: "LocalOS-ի սակագները" })).toBeInTheDocument();
    expect(screen.getByText('Ընտրեք, թե որ բիզնես խնդիրներում LocalOS-ը պետք է օգնի ձեզ')).toBeInTheDocument();
    expect(screen.getByText('$15 /ամիս')).toBeInTheDocument();
    expect(screen.queryByText('Choose the business tasks you want LocalOS to help with')).toBeNull();
  });
});
