export function slugify(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[^\w\s-]/g, "")
    .trim()
    .replace(/\s+/g, "_")
    .toLowerCase();
}

export function normalizeWhitespace(value: string | null | undefined): string {
  return (value ?? "").replace(/\s+/g, " ").trim();
}

export function readText(node: Element | null): string {
  return normalizeWhitespace(node?.textContent);
}

export function parseEuroValue(text: string | null | undefined): number | null {
  const normalized = normalizeWhitespace(text);
  const match = normalized.match(/(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*EUR/i);
  if (!match) {
    return null;
  }

  const numeric = match[1].replace(/\./g, "").replace(",", ".");
  const value = Number.parseFloat(numeric);
  return Number.isFinite(value) ? value : null;
}

export function computeAgeBand(dateText: string | null | undefined, now = new Date()): string | null {
  const normalized = normalizeWhitespace(dateText);
  const match = normalized.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (!match) {
    return null;
  }

  const [, day, month, year] = match;
  const birthDate = new Date(`${year}-${month}-${day}T00:00:00`);
  if (Number.isNaN(birthDate.getTime())) {
    return null;
  }

  let age = now.getFullYear() - birthDate.getFullYear();
  const monthDiff = now.getMonth() - birthDate.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && now.getDate() < birthDate.getDate())) {
    age -= 1;
  }

  if (age < 18) {
    return "under_18";
  }
  if (age < 26) {
    return "18_25";
  }
  if (age < 36) {
    return "26_35";
  }
  if (age < 46) {
    return "36_45";
  }
  if (age < 56) {
    return "46_55";
  }
  return "56_plus";
}
