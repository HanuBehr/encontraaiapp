const LOCATION_CONNECTORS = [" em ", " no ", " na ", " nos ", " nas ", " in "] as const;

const BRAZIL_STATE_CODES = new Set([
  "AC",
  "AL",
  "AP",
  "AM",
  "BA",
  "CE",
  "DF",
  "ES",
  "GO",
  "MA",
  "MT",
  "MS",
  "MG",
  "PA",
  "PB",
  "PR",
  "PE",
  "PI",
  "RJ",
  "RN",
  "RS",
  "RO",
  "RR",
  "SC",
  "SP",
  "SE",
  "TO",
]);

export type ParsedDiscoveryQuery = {
  rawQuery: string;
  category: string;
  city: string | null;
  state: string | null;
  searchTerms: string[];
  locationQuery: string | null;
};

export function parseNaturalLanguageDiscoveryQuery(rawInput: string): ParsedDiscoveryQuery | null {
  const rawQuery = normalizeWhitespace(rawInput);
  if (!rawQuery) {
    return null;
  }

  const lowerQuery = rawQuery.toLocaleLowerCase("pt-BR");
  let splitIndex = -1;
  let matchedConnector = "";

  LOCATION_CONNECTORS.forEach((connector) => {
    const connectorIndex = lowerQuery.lastIndexOf(connector);
    if (connectorIndex > splitIndex) {
      splitIndex = connectorIndex;
      matchedConnector = connector;
    }
  });

  if (splitIndex < 0) {
    return {
      rawQuery,
      category: rawQuery,
      city: null,
      state: null,
      searchTerms: [rawQuery],
      locationQuery: null,
    };
  }

  const category = cleanFragment(rawQuery.slice(0, splitIndex));
  const location = parseLocationFragment(rawQuery.slice(splitIndex + matchedConnector.length));

  return {
    rawQuery,
    category: category || rawQuery,
    city: location.city,
    state: location.state,
    searchTerms: [category || rawQuery],
    locationQuery: location.locationQuery,
  };
}

function parseLocationFragment(rawLocation: string) {
  const location = cleanFragment(rawLocation);
  if (!location) {
    return {
      city: null,
      state: null,
      locationQuery: null,
    };
  }

  const explicitStateMatch = /^(.*?)(?:\s*[-/,]\s*|\s+\()\s*([A-Za-z]{2})\)?$/.exec(location);
  if (!explicitStateMatch) {
    return {
      city: location,
      state: null,
      locationQuery: location,
    };
  }

  const city = cleanFragment(explicitStateMatch[1]);
  const state = explicitStateMatch[2].toUpperCase();
  if (!city || !BRAZIL_STATE_CODES.has(state)) {
    return {
      city: location,
      state: null,
      locationQuery: location,
    };
  }

  return {
    city,
    state,
    locationQuery: `${city}, ${state}`,
  };
}

function cleanFragment(value: string) {
  return normalizeWhitespace(value.replace(/^[,;:\-]+/, "").replace(/[.,;:]+$/, ""));
}

function normalizeWhitespace(value: string) {
  return value.replace(/\s+/g, " ").trim();
}
