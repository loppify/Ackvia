import { AckviaApiError, getDelivery, getSubmission, listForms, listFormSubmissions } from "@/lib/api";
import type { DeliveryDetail, SubmissionDetail } from "@/lib/types";
import { ACTIVE_STATUSES, first, numericId, offsetValue, PAGE_SIZE, type DeskSnapshot, type Query, type Resource } from "./model";

const empty = <T>(): Resource<T> => ({ data: null, error: null });
const invalid = <T>(resource: string): Resource<T> => ({ data: null, error: { title: `${resource} ID is invalid`, message: "Check the resource ID in this link and try again.", status: 400 } });

export async function readResource<T>(name: string, read: () => Promise<T>): Promise<Resource<T>> {
  try {
    return { data: await read(), error: null };
  } catch (error) {
    const status = error instanceof AckviaApiError ? error.status : undefined;
    return { data: null, error: {
      title: status === 404 ? `${name} not found` : `${name} unavailable`,
      message: status === 404 ? "This resource could not be found. Check the link or choose another item." : "The Ackvia API could not return this evidence. Try refreshing.",
      status,
    } };
  }
}

export async function loadDesk(query: Query): Promise<DeskSnapshot> {
  const offset = offsetValue(query.offset);
  const formsOffset = offsetValue(query.formsOffset);
  const rawSubmission = first(query.submission);
  const rawDelivery = first(query.delivery);
  let submissionId = numericId(rawSubmission);
  let deliveryId = numericId(rawDelivery);
  const formsPromise = readResource("Forms", () => listForms({ limit: PAGE_SIZE + 1, offset: formsOffset }));
  const submissionPromise = rawSubmission
    ? submissionId ? readResource("Submission", () => getSubmission(submissionId!)) : Promise.resolve(invalid<SubmissionDetail>("Submission"))
    : Promise.resolve(empty<SubmissionDetail>());
  const deliveryPromise = rawDelivery
    ? deliveryId ? readResource("Delivery", () => getDelivery(deliveryId!)) : Promise.resolve(invalid<DeliveryDetail>("Delivery"))
    : Promise.resolve(empty<DeliveryDetail>());
  const forms = await formsPromise;
  const moreForms = (forms.data?.length ?? 0) > PAGE_SIZE;
  if (forms.data) forms.data = forms.data.slice(0, PAGE_SIZE);
  const form = first(query.form) ?? forms.data?.[0]?.id ?? "";
  const validForm = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(form);
  const submissions = form
    ? validForm ? await readResource("Submissions", () => listFormSubmissions(form, { limit: PAGE_SIZE + 1, offset })) : invalid<Awaited<ReturnType<typeof listFormSubmissions>>>("Form")
    : empty<Awaited<ReturnType<typeof listFormSubmissions>>>();
  const moreSubmissions = (submissions.data?.length ?? 0) > PAGE_SIZE;
  if (submissions.data) submissions.data = submissions.data.slice(0, PAGE_SIZE);
  let submission = await submissionPromise;
  if (!rawSubmission && submissions.data?.length) {
    submissionId = submissions.data[0].id;
    submission = await readResource("Submission", () => getSubmission(submissionId!));
  }
  let delivery = await deliveryPromise;
  if (!rawDelivery && submission.data) {
    const choices = submission.data.deliveries;
    deliveryId = (choices.find((d) => d.status === "failed" || d.status === "unknown")
      ?? choices.find((d) => ACTIVE_STATUSES.includes(d.status)) ?? choices[0])?.id ?? null;
    if (deliveryId) delivery = await readResource("Delivery", () => getDelivery(deliveryId!));
  }
  if (delivery.data && (delivery.data.submission_id !== submissionId || (submission.data && !submission.data.deliveries.some((d) => d.id === delivery.data!.id)))) {
    delivery = { data: null, error: { title: "Delivery context does not match", message: "This delivery does not belong to the selected submission.", status: 404 } };
  }
  return {
    context: { form, submission: submissionId ?? undefined, delivery: deliveryId ?? undefined, offset, formsOffset },
    forms, moreForms, submissions, moreSubmissions, submission, delivery,
    checkedAt: new Date().toISOString(),
    linkedSelection: !!rawSubmission,
  };
}
