/**
 * Verifies that when the frontend submits a request, the POST /request body
 * includes the currently-selected language field.
 */
import { describe, it, expect } from "vitest";
import { screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import App from "../../src/App";
import { renderWithI18n } from "../../src/test/renderWithI18n";
import { server } from "../../src/test/server";

describe("request language", () => {
  it("includes the selected language in the POST /request body", async () => {
    const user = userEvent.setup();
    let capturedBody: unknown = null;

    // Override the POST /request handler to capture the body before responding
    server.use(
      http.post("/api/request", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({ request_id: "test-rid-lang" });
      }),
    );

    renderWithI18n(<App />, "en");

    await act(async () => {
      await user.type(screen.getByRole("textbox"), "compute H2 ground state");
      await user.click(screen.getByRole("button", { name: "Send" }));
    });

    expect(capturedBody).toMatchObject({
      raw_text: "compute H2 ground state",
      language: "en",
    });
  });

  it("sends the selected language (zh) in the POST /request body", async () => {
    const user = userEvent.setup();
    let capturedBody: unknown = null;

    // Override the POST /request handler to capture the body before responding
    server.use(
      http.post("/api/request", async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({ request_id: "test-rid-lang-zh" });
      }),
    );

    renderWithI18n(<App />, "zh");

    await act(async () => {
      await user.type(screen.getByRole("textbox"), "计算 H2 基态能量");
      await user.click(screen.getByRole("button", { name: "发送" }));
    });

    expect(capturedBody).toMatchObject({
      raw_text: "计算 H2 基态能量",
      language: "zh",
    });
  });
});
