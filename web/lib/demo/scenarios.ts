import type { DiscoveryLeadCandidate } from "@/lib/api/types";
import type { Locale } from "@/lib/i18n/translations";
import { normalize } from "@/lib/demo/fixtures";

export type DemoGuidedSearch = {
  query: string;
  label: string;
  description: string;
};

export type DemoScenario = DemoGuidedSearch & {
  id: string;
  locale: Locale;
  city: string;
  state: string;
  country: string;
  latitude: number;
  longitude: number;
  categoryKeywords: string[];
  locationKeywords: string[];
  candidates: DiscoveryLeadCandidate[];
};

const demoScenarios: DemoScenario[] = [
  scenario({
    id: "pt-dentists-sao-paulo",
    locale: "pt-BR",
    query: "dentistas em São Paulo",
    label: "Dentistas em São Paulo",
    description: "Clínicas odontológicas com contatos e sites variados.",
    city: "São Paulo",
    state: "SP",
    country: "Brazil",
    latitude: -23.5505,
    longitude: -46.6333,
    categoryKeywords: ["dentista", "dentistas", "odontologia", "odonto", "dental"],
    candidates: [
      candidate("Prime Odonto Jardins", "Clínica odontológica", "São Paulo", "SP", "https://primeodonto.example", "agenda@primeodonto.example", "+55 11 94002-5101", "https://instagram.com/primeodonto", "Alameda Santos, 1100"),
      candidate("Dental Care Pinheiros", "Clínica odontológica", "São Paulo", "SP", "https://dentalpinheiros.example", null, "+55 11 94002-5102", "https://instagram.com/dentalpinheiros", "Rua dos Pinheiros, 560"),
      candidate("Sorriso Norte Clinic", "Dentista", "São Paulo", "SP", null, null, "+55 11 94002-5103", null, "Av. Braz Leme, 900"),
      candidate("Implante Vila Madalena", "Implantes dentários", "São Paulo", "SP", "https://implantevila.example", "contato@implantevila.example", "+55 11 94002-5104", null, "Rua Harmonia, 420"),
    ],
  }),
  scenario({
    id: "pt-restaurants-campinas",
    locale: "pt-BR",
    query: "restaurantes em Campinas",
    label: "Restaurantes em Campinas",
    description: "Restaurantes e cafés com presença digital parcial.",
    city: "Campinas",
    state: "SP",
    country: "Brazil",
    latitude: -22.9056,
    longitude: -47.0608,
    categoryKeywords: ["restaurante", "restaurantes", "bistro", "bistrô", "cafe", "café", "food"],
    candidates: [
      candidate("Mesa Clara Restaurante", "Restaurante", "Campinas", "SP", "https://mesaclara.example", "contato@mesaclara.example", "+55 19 94002-6101", "https://instagram.com/mesaclara", "Rua Conceição, 340"),
      candidate("Brasa Urbana Campinas", "Restaurante", "Campinas", "SP", "https://brasaurbana.example", null, "+55 19 94002-6102", "https://instagram.com/brasaurbana", "Av. Norte Sul, 1220"),
      candidate("Café Alameda", "Café", "Campinas", "SP", null, null, "+55 19 94002-6103", null, "Av. Júlio de Mesquita, 80"),
      candidate("Cantina Ponte Velha", "Restaurante italiano", "Campinas", "SP", "https://pontevelha.example", "reservas@pontevelha.example", "+55 19 94002-6104", null, "Rua Barão de Jaguara, 230"),
    ],
  }),
  scenario({
    id: "pt-aesthetic-rio",
    locale: "pt-BR",
    query: "clínicas de estética no Rio de Janeiro",
    label: "Clínicas de estética no Rio",
    description: "Clínicas com Instagram, WhatsApp e candidatos CNPJ fictícios.",
    city: "Rio de Janeiro",
    state: "RJ",
    country: "Brazil",
    latitude: -22.9068,
    longitude: -43.1729,
    categoryKeywords: ["estetica", "estética", "clinica", "clínica", "beleza", "dermal", "aesthetic"],
    candidates: [
      candidate("Vitta Pele Ipanema", "Clínica de estética", "Rio de Janeiro", "RJ", "https://vittapele.example", "hello@vittapele.example", "+55 21 94002-7201", "https://instagram.com/vittapele", "Rua Visconde de Pirajá, 450"),
      candidate("Nobile Estética Rio", "Clínica de beleza", "Rio de Janeiro", "RJ", "https://nobilerio.example", null, "+55 21 94002-7202", "https://instagram.com/nobilerio", "Av. das Américas, 3000"),
      candidate("Essenza Derm Center", "Dermatologia estética", "Rio de Janeiro", "RJ", null, null, "+55 21 94002-7203", null, "Rua Voluntários da Pátria, 180"),
      candidate("Forma Leblon Clinic", "Estética avançada", "Rio de Janeiro", "RJ", "https://formaleblon.example", "agenda@formaleblon.example", null, "https://instagram.com/formaleblon", "Av. Ataulfo de Paiva, 620"),
    ],
  }),
  scenario({
    id: "pt-construction-bh",
    locale: "pt-BR",
    query: "materiais de construção em Belo Horizonte",
    label: "Materiais de construção em BH",
    description: "Distribuidores e lojas com perfil B2B.",
    city: "Belo Horizonte",
    state: "MG",
    country: "Brazil",
    latitude: -19.9167,
    longitude: -43.9345,
    categoryKeywords: ["material", "materiais", "construcao", "construção", "ferragens", "obra", "building", "construction"],
    candidates: [
      candidate("Construminas Savassi", "Materiais de construção", "Belo Horizonte", "MG", "https://construminas.example", "vendas@construminas.example", "+55 31 94002-8101", null, "Av. do Contorno, 6100"),
      candidate("BH Ferragens Pro", "Ferragens", "Belo Horizonte", "MG", "https://bhferragens.example", null, "+55 31 94002-8102", "https://instagram.com/bhferragens", "Rua Curitiba, 900"),
      candidate("Depósito Serra Verde", "Depósito de materiais", "Belo Horizonte", "MG", null, null, "+55 31 94002-8103", null, "Av. Cristiano Machado, 2100"),
      candidate("Casa Forte Acabamentos", "Acabamentos", "Belo Horizonte", "MG", "https://casafortebh.example", "orcamentos@casafortebh.example", null, null, "Rua São Paulo, 1120"),
    ],
  }),
  scenario({
    id: "en-dental-lisbon",
    locale: "en",
    query: "dental clinics in Lisbon",
    label: "Dental clinics in Lisbon",
    description: "European clinic leads with mixed contact coverage.",
    city: "Lisbon",
    state: "Lisbon",
    country: "Portugal",
    latitude: 38.7223,
    longitude: -9.1393,
    categoryKeywords: ["dentist", "dentists", "dental", "clinic", "clinics", "orthodontic"],
    candidates: [
      candidate("Alfama Dental Care", "Dental clinic", "Lisbon", "Lisbon", "https://alfamadental.example", "hello@alfamadental.example", "+351 210 000 101", "https://instagram.com/alfamadental", "Rua da Prata 120"),
      candidate("Tejo Smile Studio", "Dental clinic", "Lisbon", "Lisbon", "https://tejosmile.example", null, "+351 210 000 102", "https://instagram.com/tejosmile", "Av. da Liberdade 220"),
      candidate("Chiado Orthodontics", "Orthodontic clinic", "Lisbon", "Lisbon", null, null, "+351 210 000 103", null, "Rua Garrett 42"),
      candidate("LX Implant Center", "Dental implants", "Lisbon", "Lisbon", "https://lximplant.example", "care@lximplant.example", null, null, "Av. Fontes Pereira de Melo 35"),
    ],
  }),
  scenario({
    id: "en-restaurants-barcelona",
    locale: "en",
    query: "restaurants in Barcelona",
    label: "Restaurants in Barcelona",
    description: "Restaurants with websites, Instagram and missing-contact cases.",
    city: "Barcelona",
    state: "Catalonia",
    country: "Spain",
    latitude: 41.3851,
    longitude: 2.1734,
    categoryKeywords: ["restaurant", "restaurants", "bistro", "cafe", "tapas", "food"],
    candidates: [
      candidate("Rambla Table", "Restaurant", "Barcelona", "Catalonia", "https://ramblatable.example", "reservations@ramblatable.example", "+34 930 000 201", "https://instagram.com/ramblatable", "Carrer de Mallorca 180"),
      candidate("Gracia Tapas House", "Tapas restaurant", "Barcelona", "Catalonia", "https://graciatapas.example", null, "+34 930 000 202", "https://instagram.com/graciatapas", "Carrer de Verdi 60"),
      candidate("Poble Sec Kitchen", "Mediterranean restaurant", "Barcelona", "Catalonia", null, null, "+34 930 000 203", null, "Carrer de Blai 22"),
      candidate("Born Market Bistro", "Bistro", "Barcelona", "Catalonia", "https://bornbistro.example", "events@bornbistro.example", null, null, "Passeig del Born 15"),
    ],
  }),
  scenario({
    id: "en-aesthetic-london",
    locale: "en",
    query: "aesthetic clinics in London",
    label: "Aesthetic clinics in London",
    description: "Beauty and wellness businesses with review-ready metadata.",
    city: "London",
    state: "England",
    country: "United Kingdom",
    latitude: 51.5072,
    longitude: -0.1276,
    categoryKeywords: ["aesthetic", "aesthetics", "beauty", "skin", "clinic", "clinics", "wellness"],
    candidates: [
      candidate("Mayfair Skin Lab", "Aesthetic clinic", "London", "England", "https://mayfairskin.example", "bookings@mayfairskin.example", "+44 20 0000 301", "https://instagram.com/mayfairskin", "Davies Street 18"),
      candidate("Shoreditch Glow Clinic", "Beauty clinic", "London", "England", "https://shoreditchglow.example", null, "+44 20 0000 302", "https://instagram.com/shoreditchglow", "Great Eastern Street 95"),
      candidate("Chelsea Derm Studio", "Skin care clinic", "London", "England", null, null, "+44 20 0000 303", null, "King's Road 210"),
      candidate("Kensington Aesthetics", "Aesthetic clinic", "London", "England", "https://kensingtonaesthetics.example", "hello@kensingtonaesthetics.example", null, null, "High Street Kensington 77"),
    ],
  }),
  scenario({
    id: "en-solar-berlin",
    locale: "en",
    query: "solar installers in Berlin",
    label: "Solar installers in Berlin",
    description: "B2B installation companies with website recovery examples.",
    city: "Berlin",
    state: "Berlin",
    country: "Germany",
    latitude: 52.52,
    longitude: 13.405,
    categoryKeywords: ["solar", "installer", "installers", "photovoltaic", "pv", "energy", "energia"],
    candidates: [
      candidate("Spree Solar Technik", "Solar installer", "Berlin", "Berlin", "https://spreesolar.example", "sales@spreesolar.example", "+49 30 0000 401", null, "Invalidenstraße 90"),
      candidate("Kreuzberg PV Systems", "Photovoltaic installer", "Berlin", "Berlin", "https://kreuzbergpv.example", null, "+49 30 0000 402", "https://instagram.com/kreuzbergpv", "Oranienstraße 140"),
      candidate("Mitte Energy Works", "Solar energy contractor", "Berlin", "Berlin", null, null, "+49 30 0000 403", null, "Torstraße 55"),
      candidate("Neukölln Roof Solar", "Solar contractor", "Berlin", "Berlin", "https://neukoellnsolar.example", "info@neukoellnsolar.example", null, null, "Karl-Marx-Straße 120"),
    ],
  }),
];

export function getDemoGuidedSearches(locale: Locale): DemoGuidedSearch[] {
  return demoScenarios
    .filter((scenarioItem) => scenarioItem.locale === locale)
    .map(({ query, label, description }) => ({ query, label, description }));
}

export function matchDemoScenario(rawQuery: string, locationQuery: string | null | undefined) {
  const query = normalize(`${rawQuery} ${locationQuery ?? ""}`);
  return demoScenarios.find((scenarioItem) => {
    const categoryMatches = scenarioItem.categoryKeywords.some((keyword) => query.includes(normalize(keyword)));
    const locationMatches = scenarioItem.locationKeywords.some((keyword) => query.includes(normalize(keyword)));
    return categoryMatches && locationMatches;
  }) ?? null;
}

export function getDemoScenarioLeads() {
  return demoScenarios.flatMap((scenarioItem, scenarioIndex) =>
    scenarioItem.candidates.slice(0, 2).map((candidateValue, candidateIndex) => ({
      candidate: candidateValue,
      scenario: scenarioItem,
      id: 201 + scenarioIndex * 10 + candidateIndex,
    })),
  );
}

function scenario(input: Omit<DemoScenario, "locationKeywords">): DemoScenario {
  return {
    ...input,
    locationKeywords: [input.city, input.state, input.country],
  };
}

function candidate(
  name: string,
  category: string,
  city: string,
  state: string,
  website: string | null,
  email: string | null,
  phone: string | null,
  instagram: string | null,
  address: string,
): DiscoveryLeadCandidate {
  const domain = website ? new URL(website).hostname : null;
  return {
    business_name: name,
    normalized_business_name: normalize(name),
    category,
    address,
    neighborhood: null,
    city,
    state,
    postal_code: null,
    latitude: null,
    longitude: null,
    website,
    domain,
    email,
    phone,
    whatsapp: phone,
    instagram,
    google_maps_url: `https://maps.google.com/?q=${encodeURIComponent(`${name} ${city}`)}`,
    google_place_id: `demo-${normalize(name).replace(/\s+/g, "-")}`,
    source_provider: "demo",
    source_url: null,
    lead_source_type: "demo_seed",
  };
}
