import { api } from "./client";
import type { RentalListingList } from "./types";

export const getRentalListings = () =>
  api<RentalListingList>("/rental-listings?data_mode=live&limit=500");
