"""Generate deterministic, entirely synthetic, group-separated sample datasets."""

import csv
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# Each five-message family describes one scenario with distinct paraphrases. Entire
# families stay on one side of the split, preventing close template variants leaking.
FAMILIES: dict[str, dict[str, tuple[str, ...]]] = {
"LOW": {
"resume_request": (
"Thanks for applying. Please email your resume and a link to your portfolio so our recruiting team can review your experience.",
"We received your application. Could you share an up-to-date CV and a public work sample before we arrange a conversation?",
"The hiring team would like to read your resume and see a few projects from your portfolio.",
"Please attach your CV to the application thread; a recruiter will follow up if your background fits the role.",
"To help us review your application, send your resume and any public portfolio links you would like us to consider.",),
"interview_schedule": (
"Would Tuesday or Thursday suit you for a 30-minute video interview with the engineering team? Let us know what works.",
"We would like to schedule an interview next week. Please share two time windows when you are available.",
"Your application has moved to the interview stage. Choose a convenient slot from the calendar on our careers page.",
"Can you meet the hiring panel on Friday afternoon? If not, suggest another time that fits your schedule.",
"The recruiter is available for a short introductory call next week. Reply with your preferred day and time.",),
"application_update": (
"Your application is under review. We expect to update candidates about the next stage by the end of next month.",
"We have received your materials and will contact shortlisted applicants after the review period closes.",
"The team is still reviewing applications. You can check the status through the careers portal at any time.",
"Thanks for your interest. The hiring process has several stages, and we will send an update when the first review is complete.",
"Your application is in the queue for review. There is no need to respond until the recruiting team contacts you.",),
"resume_interview_context": (
"Please bring a copy of your resume to the interview so the panel can discuss your projects and experience.",
"Before our video conversation, review the role description and have your portfolio ready if you want to share it.",
"The first interview is a discussion about your experience. No documents are needed beyond the resume already in your application.",
"We look forward to meeting you. The interview will cover the role and leave time for your questions.",
"Your interview is confirmed. A calendar invitation will arrive from the company's recruiting system.",),
"no_fee_and_safety": (
"There is no application fee for this position. Our recruiters will never ask for a password or one-time code.",
"Applying and interviewing are free. Please do not pay anyone who claims they can secure this role for you.",
"For your security, we do not request OTPs or account passwords during recruitment. Contact the careers team with questions.",
"You do not need to buy training or equipment to apply. Any later onboarding steps will come through the official portal.",
"Our recruitment process does not involve candidate payments. Check the careers page if you need to confirm this notice.",),
"job_details": (
"The internship is hybrid, runs for twelve weeks, and includes a monthly stipend. Interviews begin after the application window.",
"This role is based in the design group and has a paid training period. The full job description is on our careers site.",
"The position is a summer placement with a fixed term. Review the requirements and apply through the official job page.",
"The team works from the campus office three days per week. Compensation and responsibilities are listed in the posting.",
"The internship includes mentorship and a project review. You can ask the recruiter about the schedule during your interview.",),
"ordinary_deadline": (
"Applications close on the date shown on the careers page. Please submit your resume there if you would like to be considered.",
"The role remains open through the posted deadline. The application form accepts updates until that date.",
"Please apply before the listed closing date so the hiring panel can include your materials in its review.",
"The job posting shows the application deadline and required experience. There is no need to contact the recruiter urgently.",
"We will review applications after the advertised closing date and reach out to selected candidates.",),
"normal_selection": (
"After two interviews and a technical exercise, the panel has selected you for the next stage of the process.",
"The hiring team would like to invite you to a second interview after reviewing your resume and initial discussion.",
"Your interview went well. The team will complete reference checks before making a final decision.",
"You have advanced to the assessment stage. Instructions will be available in your candidate portal.",
"Following the panel interview, we would like to discuss the role and answer your questions in a final meeting.",),
"verification_guidance": (
"Check that recruiter messages come from the domain published on the employer's official careers page.",
"You can verify this vacancy by navigating to the company's website yourself and searching its open roles.",
"If you are unsure whether a message is genuine, contact the recruiting office using the phone number on its official site.",
"Our careers portal lists every current opening. Search there rather than relying on an unsolicited link.",
"The hiring team can confirm interview details through the contact page linked from the employer's main website.",),
"reschedule": (
"The interviewer needs to move your meeting by one day. Please use the calendar invitation to choose another available slot.",
"We need to reschedule your interview. Reply with a couple of times that work for you later this week.",
"A panel member is unavailable, so we have moved the discussion to the time shown in your updated calendar invite.",
"Could we shift your interview to Monday morning? If that does not work, suggest another convenient time.",
"Your call has been moved to the following week. The recruiter will send a revised meeting invitation.",),
"application_acknowledgement": (
"Thank you for applying. This is an automatic acknowledgement and no action is needed until we contact you.",
"We have received your application successfully. You can view its status by signing in to the candidate portal.",
"Your submission is complete. The recruiting team will review it and get in touch about any next steps.",
"Application received. Please allow the hiring team time to assess the materials before following up.",
"The portal has recorded your application. A confirmation is available in your candidate account.",),
"interview_preparation": (
"For your interview, think about a project you enjoyed and how you approached a challenge on the team.",
"The panel will ask about your experience and interests. You may use examples from coursework or personal projects.",
"There is no test to purchase or prepare for. The first meeting is a conversation with the hiring team.",
"Please review the role description before the interview and prepare any questions you have about the position.",
"The recruiter has shared the interview agenda in your calendar invitation. Contact us if the link does not work.",),
},
"MEDIUM": {
"unusually_fast_selection": (
"Your profile was selected before an interview. Please confirm that you are still interested so we can explain the next step.",
"We have shortlisted your application unusually quickly and would like to arrange a call to discuss the role and process.",
"A recruiter says you are preselected, although no interview has taken place. Ask for the official job posting before proceeding.",
"You have been marked as a preferred candidate before meeting the team. We can provide more details about the selection process.",
"The message says your application passed initial review in minutes. Verify the opening through the employer's careers site.",),
"soft_deadline": (
"Please confirm your interest by this evening so we can keep your application in the current review group.",
"The recruiter asks for a reply within a few hours, though no sensitive information or payment is requested.",
"We are moving quickly and would appreciate an answer today about whether you want to continue the conversation.",
"A message requests confirmation before tomorrow morning to reserve an interview slot. Check with the official recruiting team.",
"The sender says the shortlist closes tonight and asks you to respond soon about your availability.",),
"personal_channel": (
"The recruiter wants to move the conversation to a personal messaging account before sharing the full job description.",
"We can discuss the internship on a messaging app. The sender has not provided an official careers page for the vacancy.",
"A contact says to continue by chat on a personal account, while the company role is not linked in the message.",
"The sender asks you to message a private account to receive more information about an unnamed opening.",
"Before arranging an interview, the recruiter suggests a personal chat and gives no company contact page.",),
"limited_verification": (
"The recruiter says the company site is being updated and asks you to rely on this message for the role details.",
"A sender describes an opening but does not share a job listing or a way to contact the employer's recruiting office.",
"The message says the vacancy is confidential and gives only a brief title. Ask for a public role description.",
"A recruiter claims to represent a large employer but provides no official profile or careers link to confirm the opening.",
"The sender asks you to trust their selection note while details of the interview and team remain unclear.",),
"identity_early_request": (
"Before the first interview, the recruiter asks you to upload an identity document to an unconfirmed form.",
"A message requests a scan of your PAN card at the application stage, without linking to a verified employer portal.",
"The sender asks for an Aadhaar copy before explaining the role or arranging a conversation.",
"An identity document is requested during initial screening. Confirm the employer and secure process before sharing it.",
"The recruiter wants an ID image before any interview has been scheduled. Verify the request independently first.",),
"secrecy_nudge": (
"The sender asks you not to contact the company office until they have finished reviewing your application.",
"Please keep this recruitment conversation private and do not ask the main HR team about the opening yet.",
"A recruiter tells you not to discuss the role with other company staff before receiving more details.",
"The message asks you to wait before contacting the listed employer because the vacancy is supposedly sensitive.",
"You are asked to keep the selection notice to yourself while the sender prepares a formal explanation.",),
"vague_job_claim": (
"A recruiter says you have been chosen for a remote role but has not provided duties, team details, or an interview plan.",
"The message promises an internship after a short chat, but the employer and responsibilities are not clearly named.",
"A sender says your application is approved for a role that is not described in a public job listing.",
"You are told that a position is reserved for you, though the message gives few details about the work.",
"The recruiter claims the role is ready for you but has not explained the selection stages or reporting team.",),
"document_before_offer": (
"The recruiter asks for your full date of birth and home address before sharing an interview invitation.",
"An early screening message asks for personal profile details that do not appear necessary to schedule a first interview.",
"Before an interview, the sender wants additional personal details through a form that is not on the company website.",
"The recruiter asks for your complete residential details before telling you which team owns the role.",
"A candidate form requests extra personal information at the initial contact stage. Confirm who controls the form first.",),
"compressed_process": (
"The sender says the full hiring process can be completed in one brief chat and asks you to decide quickly.",
"An offer is described as nearly ready after one short message exchange, with no interview plan explained.",
"The recruiter says there is no time for the normal selection stages and asks for a quick confirmation of interest.",
"A message describes instant onboarding but leaves the job duties and reporting manager unspecified.",
"The sender promises a fast selection route and asks you to reply today before the vacancy is publicly posted.",),
"unclear_fee_language": (
"A recruiter mentions a refundable onboarding deposit but has not explained the employer's normal hiring process.",
"The message refers to a possible training charge and asks you to get clarification before continuing.",
"An unclear note says some candidates cover setup costs. Verify the policy directly with the employer before replying.",
"The sender discusses a security amount in passing but does not yet provide a payment request or official role details.",
"A vague onboarding note refers to costs that may apply. Ask the employer's official HR channel to explain in writing.",),
"odd_selection_detail": (
"The message claims the interview is optional and says a decision may be made from your profile alone.",
"A sender says you are effectively selected, but offers no details about the interview or assessment stage.",
"The recruiter says the team can skip its usual interviews for your application without explaining why.",
"An invitation describes a guaranteed place before the hiring panel has spoken with candidates.",
"You are told that selection is almost certain despite no discussion with the hiring team.",),
"verification_delay": (
"The recruiter says official details will be available later and asks you to continue the conversation in the meantime.",
"A message asks you to wait before checking the company website because the role is not listed there yet.",
"The sender promises a public job description after you have confirmed interest in the offer.",
"A recruiter says the company cannot confirm the position through its main number until a later date.",
"The message delays sharing the employer's official contact details until after an initial response.",),
},
"HIGH": {
"aadhaar_pan_harvest": (
"To reserve this internship, send a photo of your Aadhaar card before the interview. The offer expires tonight.",
"Upload your PAN card now to keep the job offer active; the recruiter says the selection will be canceled if you wait.",
"We need your national identity document by message today to release the appointment letter.",
"The sender requests a passport scan before any interview and says not to contact the company office.",
"Share your government ID number immediately or your place on the hiring list will be withdrawn.",),
"bank_detail_harvest": (
"Send your bank account number and IFSC code to this recruiter before the first interview to confirm your stipend.",
"The sender asks for a bank statement and account details by chat to activate a job application.",
"Provide your debit card information now so payroll can reserve your internship payment.",
"To process selection, send your account number and UPI ID to the recruiter through this private message.",
"The message requests routing and bank details before an offer is signed, and pressures you to reply today.",),
"candidate_fee": (
"Pay a refundable registration fee today to secure your interview slot; the offer may be canceled if you delay.",
"Transfer the processing deposit before the recruiter releases your appointment letter.",
"A training fee is mandatory before you can start this internship. Send the money to the recruiter now.",
"Pay the security deposit by tonight to keep your selection active. Do not call the company office about this fee.",
"The sender demands an onboarding charge before any interview and says the vacancy closes within hours.",),
"otp_password": (
"Send the OTP from your phone to the recruiter so they can verify your candidate account.",
"Reply with your password and one-time sign-in code to confirm your identity for this job.",
"The recruiter says they need the verification code sent to your account to release the offer.",
"Share your login credentials in this chat so the hiring agent can finish your application.",
"Text the account recovery code to the recruiter immediately to keep your profile active.",),
"id_secrecy_pressure": (
"Send your Aadhaar scan today and do not contact HR; the offer will be withdrawn if you tell anyone.",
"The sender asks for a passport image by private chat and says the company must not be contacted.",
"Upload your PAN card before midnight. Keep this request secret from the employer's recruiting office.",
"Provide your national ID number now or your offer will be canceled; do not ask the main HR team.",
"A recruiter demands your identity card and warns you not to verify the selection with anyone at the company.",),
"fee_secrecy_urgency": (
"Pay the placement fee within one hour and do not call the listed employer to confirm this instruction.",
"Send the processing money now. Keep the payment request private or the offer will be canceled.",
"The sender demands a deposit today and tells you not to discuss it with the company's HR staff.",
"Transfer the registration charge before midnight; the recruiter says outside confirmation will cost you the role.",
"You must pay an interview fee immediately and keep the request secret from other company employees.",),
"bank_cancel_threat": (
"Provide your bank account details within an hour or the recruiter will cancel your selected position.",
"The sender threatens to withdraw the offer unless you send your account number and card details today.",
"Share the UPI and bank information now to prevent your internship place from being forfeited.",
"The offer will be revoked unless you provide bank details through this unverified message before noon.",
"A recruiter says payroll needs your account credentials immediately or you will lose the job.",),
"credential_fee_combo": (
"Pay the verification charge and send the OTP from your phone so the recruiter can activate your account.",
"The agent requests a password and processing fee to complete selection before the deadline tonight.",
"Send money and your account recovery code now; the sender says this is required to release the offer.",
"To confirm the interview, pay a security charge and reply with the one-time code you just received.",
"The message combines an upfront recruitment payment with a request for your login password.",),
"identity_financial_combo": (
"Upload your government ID and bank statement to this private form before the recruiter arranges an interview.",
"The sender asks for a passport scan together with your account number to prepare a job offer.",
"Provide your PAN details and debit card number through chat for candidate verification.",
"Share your identity document and bank information immediately; do not wait for the official portal.",
"The recruiter wants your national ID and UPI details by message before the selection process is complete.",),
"threatened_offer": (
"Your offer will be canceled unless you pay the training deposit in the next two hours.",
"Send a photo of your identity document now or you will forfeit the selected position.",
"The recruiter says your job offer will be withdrawn unless you share the one-time code immediately.",
"Provide the requested bank details by tonight or the company will cancel your appointment letter.",
"A sender threatens to revoke your internship if you do not transfer the processing fee today.",),
"fake_interview_payment": (
"You are selected without an interview. Pay the refundable security amount today to confirm your position.",
"The recruiter guarantees a job without an assessment but requires an upfront registration payment.",
"A message promises instant selection with no interview and asks for a training deposit before sharing the contract.",
"Your position is guaranteed without speaking to the team, once you send the processing fee now.",
"The sender claims you passed without an interview and demands payment before giving any employer details.",),
"credential_secrecy": (
"Send the OTP to this recruiter and do not contact the company help desk while your account is being verified.",
"Share your password privately; the agent says not to tell HR because this is a confidential hiring step.",
"Reply with the login code and keep the request secret from the company's recruitment staff.",
"The sender requests your account recovery code and warns that contacting the employer will cancel selection.",
"Provide your one-time passcode immediately. The message says not to discuss this verification with anyone.",),
},
}


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    rows = []
    # Fixed family allocation gives 2/3 train and 1/3 held-out within every label.
    for label, families in FAMILIES.items():
        if len(families) != 12:
            raise ValueError(f"Expected 12 scenario families for {label}, got {len(families)}")
        for family_index, (family_name, variants) in enumerate(families.items()):
            if len(variants) != 5:
                raise ValueError(f"Expected five variants for {family_name}")
            split = "train" if family_index < 8 else "test"
            for text in variants:
                rows.append({"text": text, "label": label, "family": f"{label.lower()}_{family_name}", "split": split})

    # Exact duplicates are rejected before the files are written.
    normalized = [" ".join(row["text"].casefold().split()) for row in rows]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Duplicate synthetic messages detected")
    train_rows = [row for row in rows if row["split"] == "train"]
    test_rows = [row for row in rows if row["split"] == "test"]
    near_pairs = [
        (left["family"], right["family"])
        for left in train_rows for right in test_rows
        if SequenceMatcher(None, " ".join(left["text"].casefold().split()),
                           " ".join(right["text"].casefold().split())).ratio() >= 0.82
    ]
    if near_pairs:
        raise ValueError(f"Near-duplicate messages cross the split (similarity >= .82): {near_pairs[:3]}")
    for split in ("train", "test"):
        subset = [row for row in rows if row["split"] == split]
        path = DATA / f"{split}.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=("text", "label", "family"))
            writer.writeheader()
            writer.writerows({key: row[key] for key in writer.fieldnames} for row in subset)
    train_families = {row["family"] for row in rows if row["split"] == "train"}
    test_families = {row["family"] for row in rows if row["split"] == "test"}
    if train_families & test_families:
        raise ValueError("Scenario family leaked across split")
    print(f"Generated {len(rows)} synthetic messages: train={len(train_rows)}, held-out={len(test_rows)}; family-disjoint, stratified, and no cross-split text pair at similarity >= .82.")


if __name__ == "__main__":
    main()
