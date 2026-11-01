export function scratchCount(draft) {
  return Object.keys(draft?.observation_scratch || {}).length;
}
export function completionRequest(form, draft, review = null) {
  const result = { form, scratch_count: scratchCount(draft) };
  if (review) {
    result.review_token = review.review_token;
    result.acknowledge_missing = Boolean(review.acknowledged);
  }
  return result;
}
