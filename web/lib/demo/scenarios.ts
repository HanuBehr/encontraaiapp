import type { DiscoveryLeadCandidate } from "@/lib/api/types";
import type { Locale } from "@/lib/i18n/translations";
import { normalize } from "@/lib/demo/fixtures";

export type DemoGuidedSearch = {
  query: string;
  label: string;
  description: string;
  city: string;
  state: string;
  resultCount: number;
  websiteCount: number;
};

export type DemoScenario = Omit<DemoGuidedSearch, "resultCount" | "websiteCount"> & {
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
    id: "pt-odontologia-sao-paulo",
    locale: "pt-BR",
    query: "clínicas odontológicas em São Paulo",
    label: "Clínicas odontológicas em São Paulo",
    description: "Clínicas com sites, WhatsApp, Instagram e alguns cadastros incompletos para revisão.",
    city: "São Paulo",
    state: "SP",
    country: "Brazil",
    latitude: -23.5505,
    longitude: -46.6333,
    categoryKeywords: ["dentista", "dentistas", "odontologia", "odontológica", "odonto", "dental", "clínica"],
    candidates: candidateSet({
      city: "São Paulo",
      state: "SP",
      phonePrefix: "+55 11 94",
      streetNames: ["Alameda Santos", "Rua dos Pinheiros", "Avenida Paulista", "Rua Harmonia", "Avenida Rebouças"],
      categories: ["Clínica odontológica", "Ortodontia", "Implantes dentários", "Dentista", "Odontologia estética"],
      names: [
        "Prime Odonto Jardins", "Dental Care Pinheiros", "Sorriso Norte Clinic", "Implante Vila Madalena", "Alameda Smile Studio",
        "Paulista Oral Design", "Vila Nova Odonto", "Higienópolis Dental Hub", "Moema Dental Care", "Itaim Smile Center",
        "Clínica Dente Vivo", "Perdizes Odontologia", "Brooklin Ortho Lab", "Santana Dental Prime", "Aclimação Sorriso",
        "Tatuapé Oral Studio", "Vila Mariana Dental", "Jardim Europa Odonto", "Lapa Dental House", "Liberdade Smile Lab",
      ],
    }),
  }),
  scenario({
    id: "pt-restaurantes-campinas",
    locale: "pt-BR",
    query: "restaurantes em Campinas",
    label: "Restaurantes em Campinas",
    description: "Restaurantes, cafés e casas de eventos com níveis variados de presença digital.",
    city: "Campinas",
    state: "SP",
    country: "Brazil",
    latitude: -22.9056,
    longitude: -47.0608,
    categoryKeywords: ["restaurante", "restaurantes", "bistrô", "bistro", "café", "cafe", "bar", "food"],
    candidates: candidateSet({
      city: "Campinas",
      state: "SP",
      phonePrefix: "+55 19 94",
      streetNames: ["Rua Conceição", "Avenida Norte Sul", "Rua Barão de Jaguara", "Avenida Júlio de Mesquita", "Rua José Paulino"],
      categories: ["Restaurante", "Café", "Bistrô", "Restaurante italiano", "Casa de eventos"],
      names: [
        "Mesa Clara Restaurante", "Brasa Urbana Campinas", "Café Alameda", "Cantina Ponte Velha", "Bistrô Cambuí",
        "Casa Taquaral", "Forno Norte Sul", "Jardim Gourmet Campinas", "Trattoria Vértice", "Cozinha Barão",
        "Dona Aurora Café", "Grão do Cambuí", "Mercado 130 Bistrô", "Estação Sousas", "Pátio Guanabara",
        "Boteco da Lagoa", "Rota 19 Grill", "Sabor Vila Industrial", "Quintal Anhumas", "Mesa do Bosque",
      ],
    }),
  }),
  scenario({
    id: "pt-estetica-rio",
    locale: "pt-BR",
    query: "clínicas de estética no Rio de Janeiro",
    label: "Clínicas de estética no Rio de Janeiro",
    description: "Clínicas de beleza, dermatologia estética e bem-estar com canais públicos variados.",
    city: "Rio de Janeiro",
    state: "RJ",
    country: "Brazil",
    latitude: -22.9068,
    longitude: -43.1729,
    categoryKeywords: ["estética", "estetica", "beleza", "dermatologia", "skin", "clínica", "clinica"],
    candidates: candidateSet({
      city: "Rio de Janeiro",
      state: "RJ",
      phonePrefix: "+55 21 94",
      streetNames: ["Rua Visconde de Pirajá", "Avenida das Américas", "Rua Voluntários da Pátria", "Avenida Ataulfo de Paiva", "Rua Conde de Bonfim"],
      categories: ["Clínica de estética", "Dermatologia estética", "Clínica de beleza", "Spa urbano", "Estética avançada"],
      names: [
        "Vitta Pele Ipanema", "Nobile Estética Rio", "Essenza Derm Center", "Forma Leblon Clinic", "Botafogo Skin Lab",
        "Lagoa Glow Studio", "Barra Estética Prime", "Copacabana Derma", "Tijuca Beauty Care", "Leme Skin House",
        "Gávea Aesthetic Hub", "Recreio Derm Studio", "Icaraí Glow Clinic", "Flamengo Beleza", "Jacarepaguá Skin",
        "Rio Corpo e Pele", "Jardim Oceânico Spa", "Urca Beauty Lab", "Méier Estética", "Vogue Derma Rio",
      ],
    }),
  }),
  scenario({
    id: "pt-logistica-belo-horizonte",
    locale: "pt-BR",
    query: "empresas de logística em Belo Horizonte",
    label: "Empresas de logística em Belo Horizonte",
    description: "Transportadoras, operadores e fornecedores B2B com cobertura regional.",
    city: "Belo Horizonte",
    state: "MG",
    country: "Brazil",
    latitude: -19.9167,
    longitude: -43.9345,
    categoryKeywords: ["logística", "logistica", "transportadora", "transporte", "distribuidora", "fulfillment", "entrega"],
    candidates: candidateSet({
      city: "Belo Horizonte",
      state: "MG",
      phonePrefix: "+55 31 94",
      streetNames: ["Avenida do Contorno", "Rua Curitiba", "Avenida Cristiano Machado", "Rua São Paulo", "Avenida Amazonas"],
      categories: ["Transportadora", "Operador logístico", "Distribuidora", "Entrega B2B", "Fulfillment"],
      names: [
        "Rota Minas Logística", "BH Fulfillment Hub", "Serra Verde Distribuição", "Ponto Cargo Express", "Contorno Freight",
        "Minas Last Mile", "Savassi Supply Co", "Betim Cargo Link", "Pampulha Transportes", "Horizonte Distribuição",
        "Via Minas Operações", "Cargo Norte BH", "Expresso Pampulha", "Hub Gerais", "Rodo Serra Logistics",
        "Armazém 31", "BH Crossdock", "Triângulo Cargo", "Central Mineira B2B", "Vetor Log Minas",
      ],
    }),
  }),
  scenario({
    id: "pt-materiais-curitiba",
    locale: "pt-BR",
    query: "materiais de construção em Curitiba",
    label: "Materiais de construção em Curitiba",
    description: "Lojas e fornecedores de materiais com perfil de venda local e B2B.",
    city: "Curitiba",
    state: "PR",
    country: "Brazil",
    latitude: -25.4284,
    longitude: -49.2733,
    categoryKeywords: ["materiais", "construção", "construcao", "obra", "acabamento", "ferragem", "depósito"],
    candidates: candidateSet({
      city: "Curitiba",
      state: "PR",
      phonePrefix: "+55 41 94",
      streetNames: ["Avenida Sete de Setembro", "Rua XV de Novembro", "Avenida República Argentina", "Rua Mateus Leme", "Avenida das Torres"],
      categories: ["Materiais de construção", "Loja de acabamentos", "Depósito de materiais", "Ferragens", "Home center local"],
      names: [
        "Base Forte Curitiba", "Casa Obra Batel", "Depósito Água Verde", "Torres Materiais", "Paraná Acabamentos",
        "Vila Hauer Ferragens", "Rebouças Construção", "Cabral Home Center", "Cristal Obra Fácil", "Boqueirão Materiais",
        "Portão Revestimentos", "Mercês Casa e Obra", "Juvevê Ferragens", "Pinheirinho Construção", "Santa Felicidade Materiais",
        "Alto da XV Acabamentos", "Bairro Novo Obra", "Cajuru Ferragens", "Curitiba ProBuild", "Linha Verde Materiais",
      ],
    }),
  }),
  scenario({
    id: "pt-academias-porto-alegre",
    locale: "pt-BR",
    query: "academias em Porto Alegre",
    label: "Academias em Porto Alegre",
    description: "Academias, studios e espaços fitness com presença digital mista.",
    city: "Porto Alegre",
    state: "RS",
    country: "Brazil",
    latitude: -30.0346,
    longitude: -51.2177,
    categoryKeywords: ["academia", "academias", "fitness", "pilates", "crossfit", "treino", "studio"],
    candidates: candidateSet({
      city: "Porto Alegre",
      state: "RS",
      phonePrefix: "+55 51 94",
      streetNames: ["Avenida Goethe", "Rua Padre Chagas", "Avenida Ipiranga", "Rua Mostardeiro", "Avenida Protásio Alves"],
      categories: ["Academia", "Studio fitness", "Pilates", "Treinamento funcional", "Cross training"],
      names: [
        "Moinhos Fit Studio", "Goethe Performance", "Poa Core Pilates", "Cidade Baixa Training", "Parcão Fitness",
        "Menino Deus Active", "Bela Vista Gym", "Nilo Funcional", "Auxiliadora Move", "Zenit Cross POA",
        "Ipiranga Fit Lab", "Cristal Training", "Tristeza Pilates", "Zona Sul Performance", "Higienópolis Fit",
        "Bom Fim Studio", "Petrópolis Core", "Mont Serrat Active", "Arena Guaíba", "Flow Porto Fitness",
      ],
    }),
  }),
  scenario({
    id: "en-dental-san-francisco",
    locale: "en",
    query: "dental clinics in San Francisco",
    label: "Dental clinics in San Francisco",
    description: "Bay Area clinics with mixed website, email, and social coverage.",
    city: "San Francisco",
    state: "CA",
    country: "United States",
    latitude: 37.7749,
    longitude: -122.4194,
    categoryKeywords: ["dentist", "dentists", "dental", "orthodontic", "clinic", "clinics"],
    candidates: candidateSet({
      city: "San Francisco",
      state: "CA",
      phonePrefix: "+1 415 55",
      streetNames: ["Market Street", "Mission Street", "Geary Boulevard", "Valencia Street", "Divisadero Street"],
      categories: ["Dental clinic", "Orthodontic clinic", "Cosmetic dentistry", "Dental implants", "Family dentist"],
      names: [
        "Mission Bay Dental", "Pacific Smile Studio", "Noe Valley Orthodontics", "Golden Gate Dental Care", "Soma Implant Center",
        "Marina Dental House", "Castro Smile Lab", "Richmond Family Dental", "Sunset Oral Studio", "Hayes Valley Dental",
        "Nob Hill Dentistry", "Valencia Smile Works", "Potrero Dental Group", "Embarcadero Dental", "North Beach Ortho",
        "Fillmore Dental Studio", "Twin Peaks Smile", "Union Square Dental", "Presidio Oral Care", "Dogpatch Dental Lab",
      ],
    }),
  }),
  scenario({
    id: "en-restaurants-new-york",
    locale: "en",
    query: "restaurants in New York",
    label: "Restaurants in New York",
    description: "Restaurants, cafes, and hospitality leads across dense city neighborhoods.",
    city: "New York",
    state: "NY",
    country: "United States",
    latitude: 40.7128,
    longitude: -74.006,
    categoryKeywords: ["restaurant", "restaurants", "cafe", "bistro", "bar", "hospitality", "food"],
    candidates: candidateSet({
      city: "New York",
      state: "NY",
      phonePrefix: "+1 212 55",
      streetNames: ["Broadway", "Canal Street", "Lafayette Street", "Bedford Avenue", "Amsterdam Avenue"],
      categories: ["Restaurant", "Cafe", "Bistro", "Wine bar", "Private dining"],
      names: [
        "Soho Table", "Canal Street Kitchen", "Hudson Plate", "Brooklyn Hearth", "West Village Bistro",
        "Bowery Supper Club", "Tribeca Pantry", "Flatiron Dining Room", "Chelsea Market Table", "Nolita Grill",
        "Upper West Cafe", "Dumbo Wine Kitchen", "East Village Noodles", "Midtown Lunch House", "Harlem Social Table",
        "Williamsburg Garden", "Greenpoint Bistro", "Park Slope Supper", "Astoria Plate", "Queensboro Kitchen",
      ],
    }),
  }),
  scenario({
    id: "en-aesthetic-london",
    locale: "en",
    query: "aesthetic clinics in London",
    label: "Aesthetic clinics in London",
    description: "Beauty, wellness, and skin-care businesses with review-ready metadata.",
    city: "London",
    state: "England",
    country: "United Kingdom",
    latitude: 51.5072,
    longitude: -0.1276,
    categoryKeywords: ["aesthetic", "aesthetics", "beauty", "skin", "clinic", "clinics", "wellness"],
    candidates: candidateSet({
      city: "London",
      state: "England",
      phonePrefix: "+44 20 70",
      streetNames: ["Oxford Street", "King's Road", "Great Eastern Street", "Baker Street", "Kensington High Street"],
      categories: ["Aesthetic clinic", "Skin care clinic", "Beauty clinic", "Wellness studio", "Dermal clinic"],
      names: [
        "Mayfair Skin Lab", "Shoreditch Glow Clinic", "Chelsea Derm Studio", "Kensington Aesthetics", "Soho Beauty House",
        "Marylebone Skin Works", "Islington Glow", "Notting Hill Dermal", "Camden Beauty Lab", "Clapham Skin Clinic",
        "Fulham Aesthetic Studio", "Brixton Glow Room", "Hampstead Skin Care", "Canary Wharf Derm", "Hackney Wellness Lab",
        "Victoria Beauty Clinic", "Greenwich Skin Studio", "Ealing Aesthetics", "Richmond Glow", "Battersea Derm House",
      ],
    }),
  }),
  scenario({
    id: "en-solar-berlin",
    locale: "en",
    query: "solar installers in Berlin",
    label: "Solar installers in Berlin",
    description: "Installation companies, PV contractors, and energy providers with website recovery cases.",
    city: "Berlin",
    state: "Berlin",
    country: "Germany",
    latitude: 52.52,
    longitude: 13.405,
    categoryKeywords: ["solar", "installer", "installers", "photovoltaic", "pv", "energy", "contractor"],
    candidates: candidateSet({
      city: "Berlin",
      state: "Berlin",
      phonePrefix: "+49 30 70",
      streetNames: ["Invalidenstraße", "Torstraße", "Oranienstraße", "Karl-Marx-Straße", "Prenzlauer Allee"],
      categories: ["Solar installer", "Photovoltaic installer", "Solar contractor", "Energy contractor", "Roof solar provider"],
      names: [
        "Spree Solar Technik", "Kreuzberg PV Systems", "Mitte Energy Works", "Neukölln Roof Solar", "Prenzlauer Solarhaus",
        "Charlottenburg PV", "Friedrichshain Energy", "Tempelhof Solar Group", "Wedding Grid Works", "Pankow Sun Systems",
        "Berlin Roof Power", "Solarwerk Moabit", "Lichtenberg Energy Co", "Steglitz PV Partner", "Treptow Solar Team",
        "Grünau Energy", "Reinickendorf Sun", "Adlershof Solar Lab", "Schöneberg PV", "Havel Solar Works",
      ],
    }),
  }),
  scenario({
    id: "en-logistics-amsterdam",
    locale: "en",
    query: "logistics companies in Amsterdam",
    label: "Logistics companies in Amsterdam",
    description: "B2B freight, fulfillment, and delivery operators around a major trade hub.",
    city: "Amsterdam",
    state: "North Holland",
    country: "Netherlands",
    latitude: 52.3676,
    longitude: 4.9041,
    categoryKeywords: ["logistics", "freight", "fulfillment", "delivery", "warehouse", "transport"],
    candidates: candidateSet({
      city: "Amsterdam",
      state: "North Holland",
      phonePrefix: "+31 20 70",
      streetNames: ["Herengracht", "Prinsengracht", "Wibautstraat", "De Ruijterkade", "Spaklerweg"],
      categories: ["Logistics provider", "Freight forwarder", "Fulfillment center", "Delivery operator", "Warehouse services"],
      names: [
        "Canal Freight Co", "Damrak Logistics", "North Dock Fulfillment", "Jordaan Delivery Works", "Amstel Cargo Link",
        "Zuidas Supply Chain", "Portside Freight", "Wibaut Warehouse", "Ring Road Logistics", "IJ Distribution",
        "Prinsengracht Cargo", "Westpoort Fulfillment", "Amsterdam Last Mile", "Holland Trade Logistics", "Metro Freight Hub",
        "A10 Cargo Systems", "Canal Belt Couriers", "Harbor Flow Logistics", "Nieuw-West Delivery", "Oost Freight Partner",
      ],
    }),
  }),
  scenario({
    id: "en-hotels-melbourne",
    locale: "en",
    query: "boutique hotels in Melbourne",
    label: "Boutique hotels in Melbourne",
    description: "Hospitality prospects with event, booking, and local partnership potential.",
    city: "Melbourne",
    state: "Victoria",
    country: "Australia",
    latitude: -37.8136,
    longitude: 144.9631,
    categoryKeywords: ["hotel", "hotels", "boutique", "hospitality", "accommodation", "stay"],
    candidates: candidateSet({
      city: "Melbourne",
      state: "Victoria",
      phonePrefix: "+61 3 70",
      streetNames: ["Collins Street", "Flinders Lane", "Brunswick Street", "Chapel Street", "Lygon Street"],
      categories: ["Boutique hotel", "Design hotel", "Serviced accommodation", "Hospitality group", "Urban stay"],
      names: [
        "Laneway House Hotel", "Collins Quarter Stay", "Fitzroy Rooms", "Southbank Boutique", "Carlton House Melbourne",
        "Docklands Urban Stay", "Prahran Design Hotel", "St Kilda Guest House", "Flinders Lane Suites", "Brunswick Hotel Co",
        "Yarra View Rooms", "Little Collins Stay", "Northside Boutique", "Chapel Street Hotel", "The Lygon Residence",
        "Richmond Urban Hotel", "Melbourne Garden Rooms", "Queen Victoria Stay", "Arcade House Hotel", "Port Phillip Boutique",
      ],
    }),
  }),
  scenario({
    id: "en-agencies-toronto",
    locale: "en",
    query: "marketing agencies in Toronto",
    label: "Marketing agencies in Toronto",
    description: "Service businesses with domains, public channels, and qualification signals.",
    city: "Toronto",
    state: "Ontario",
    country: "Canada",
    latitude: 43.6532,
    longitude: -79.3832,
    categoryKeywords: ["marketing", "agency", "agencies", "creative", "digital", "advertising"],
    candidates: candidateSet({
      city: "Toronto",
      state: "Ontario",
      phonePrefix: "+1 416 55",
      streetNames: ["King Street West", "Queen Street West", "Spadina Avenue", "Dundas Street", "Front Street"],
      categories: ["Marketing agency", "Creative agency", "Digital agency", "Brand studio", "Advertising agency"],
      names: [
        "King West Creative", "Queen Street Digital", "Harbourfront Agency", "Spadina Brand Studio", "Annex Growth Co",
        "Liberty Village Media", "Toronto Campaign Lab", "Yorkville Creative", "Dundas Digital Works", "Leslieville Brand House",
        "Riverside Growth Studio", "Parkdale Media Group", "North York Digital", "Bloor Creative Co", "Midtown Marketing Lab",
        "Front Street Studio", "Kensington Growth", "The Junction Agency", "Scarborough Digital", "Etobicoke Brand Works",
      ],
    }),
  }),
  scenario({
    id: "en-fitness-dublin",
    locale: "en",
    query: "fitness studios in Dublin",
    label: "Fitness studios in Dublin",
    description: "Studios, gyms, pilates spaces, and training operators with mixed contact depth.",
    city: "Dublin",
    state: "Dublin",
    country: "Ireland",
    latitude: 53.3498,
    longitude: -6.2603,
    categoryKeywords: ["fitness", "gym", "gyms", "studio", "pilates", "training", "crossfit"],
    candidates: candidateSet({
      city: "Dublin",
      state: "Dublin",
      phonePrefix: "+353 1 70",
      streetNames: ["Grafton Street", "Camden Street", "Dawson Street", "Rathmines Road", "Pearse Street"],
      categories: ["Fitness studio", "Gym", "Pilates studio", "Training studio", "Cross training"],
      names: [
        "Camden Fit Studio", "Docklands Training", "Rathmines Pilates", "Temple Bar Fitness", "Dublin Core Lab",
        "Grafton Strength", "Pearse Performance", "Smithfield Active", "Ballsbridge Fitness", "Portobello Pilates",
        "Ranelagh Training Co", "Clontarf Fit House", "Drumcondra Gym", "Stoneybatter Studio", "Merrion Fitness Lab",
        "Dublin Move Club", "Grand Canal Training", "Phoenix Park Fitness", "IFSC Strength", "Southside Core Studio",
      ],
    }),
  }),
];

export function getDemoGuidedSearches(locale: Locale): DemoGuidedSearch[] {
  return demoScenarios
    .filter((scenarioItem) => scenarioItem.locale === locale)
    .map(({ candidates, city, description, label, query, state }) => ({
      query,
      label,
      description,
      city,
      state,
      resultCount: candidates.length,
      websiteCount: candidates.filter((candidateItem) => Boolean(candidateItem.website)).length,
    }));
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
    scenarioItem.candidates.slice(0, 4).map((candidateValue, candidateIndex) => ({
      candidate: candidateValue,
      scenario: scenarioItem,
      id: 201 + scenarioIndex * 20 + candidateIndex,
    })),
  );
}

function scenario(input: Omit<DemoScenario, "locationKeywords">): DemoScenario {
  return {
    ...input,
    locationKeywords: [input.city, input.state, input.country],
  };
}

function candidateSet(input: {
  city: string;
  state: string;
  phonePrefix: string;
  streetNames: string[];
  categories: string[];
  names: string[];
}) {
  return input.names.map((name, index) => {
    const number = String(index + 1).padStart(2, "0");
    const slug = normalize(name).replace(/\s+/g, "-");
    const website = index % 5 === 2 ? null : `https://${slug}.example`;
    const email = website && index % 3 !== 1 ? `hello@${new URL(website).hostname}` : null;
    const phone = index % 7 === 3 ? null : `${input.phonePrefix}${String(1000 + index).slice(-4)}`;
    const instagram = index % 2 === 0 ? `https://instagram.com/${slug.replace(/-/g, "")}` : null;
    const street = input.streetNames[index % input.streetNames.length];
    return candidate(
      name,
      input.categories[index % input.categories.length],
      input.city,
      input.state,
      website,
      email,
      phone,
      instagram,
      `${street}, ${120 + index * 37}`,
      number,
    );
  });
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
  suffix: string,
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
    google_place_id: `demo-${normalize(name).replace(/\s+/g, "-")}-${suffix}`,
    source_provider: "demo",
    source_url: null,
    lead_source_type: "demo_seed",
  };
}
