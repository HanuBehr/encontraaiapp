import { LeadOperationsWorkspace } from "@/components/leads/LeadOperationsWorkspace";

type LeadsPageProps = {
  searchParams: Promise<{
    import_batch_id?: string | string[];
  }>;
};

export default async function LeadsPage({ searchParams }: LeadsPageProps) {
  const params = await searchParams;
  return <LeadOperationsWorkspace initialImportBatchId={parsePositiveInteger(params.import_batch_id)} />;
}

function parsePositiveInteger(value: string | string[] | undefined) {
  const candidate = Array.isArray(value) ? value[0] : value;
  if (!candidate) {
    return null;
  }
  const parsed = Number(candidate);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}
