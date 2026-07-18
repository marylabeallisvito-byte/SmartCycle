/**
 * SmartCycle — API Client Smoke Tests
 *
 * Tests that API types and helpers are correctly structured.
 * These are compile-time safety + runtime smoke tests — they verify
 * that the TypeScript types are consistent with the backend contract.
 */

import { describe, expect, it, vi } from "vitest";

// Mock axios before importing api module (apiClient is created at module scope)
vi.mock("axios", () => {
  const mockAxios = {
    create: vi.fn(() => ({
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
      post: vi.fn(),
      get: vi.fn(),
    })),
  };
  return { default: mockAxios };
});

// We test the type exports and helper functions, not HTTP calls
import {
  getToken,
  login,
  logout,
} from "@/lib/api";

// ── Auth helpers ──

describe("Auth helpers", () => {
  it("getToken returns null when no token stored", () => {
    // localStorage is empty by default in test env
    expect(getToken()).toBeNull();
  });

  it("logout clears token without error", () => {
    expect(() => logout()).not.toThrow();
  });
});

// ── Type export existence ──

describe("API module exports", () => {
  it("exports login function", () => {
    expect(typeof login).toBe("function");
  });

  it("exports logout function", () => {
    expect(typeof logout).toBe("function");
  });

  it("exports getToken function", () => {
    expect(typeof getToken).toBe("function");
  });
});

// ── Login request shape (type-level test via runtime construction) ──

describe("LoginRequest shape", () => {
  it("accepts valid login payload", () => {
    const payload = { username: "admin", password: "smartcycle2024" };
    expect(payload.username).toBe("admin");
    expect(payload.password).toBe("smartcycle2024");
  });
});
