"""Write independent, synthetic validation and adversarial challenge corpora."""

import csv
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# New scenarios written for Phase 3; they do not reuse the Phase 2 corpus.
CHALLENGE = [
    ("LEGITIMATE", "LOW", "resume", "Please attach your resume and portfolio so the hiring panel can review your application."),
    ("LEGITIMATE", "LOW", "resume", "Could you share a current CV before we schedule a first conversation?"),
    ("LEGITIMATE", "LOW", "resume", "Your application is complete. The recruiter would like to read your resume and public work samples."),
    ("LEGITIMATE", "LOW", "interview", "Would Wednesday afternoon work for a 25-minute interview with the product team?"),
    ("LEGITIMATE", "LOW", "interview", "Choose an interview slot by Friday using the calendar invitation from our careers system."),
    ("LEGITIMATE", "LOW", "interview", "The panel is available next week. Please reply with two times that suit you."),
    ("LEGITIMATE", "LOW", "deadline", "Applications close next month. Submit your materials through the role page before that date."),
    ("LEGITIMATE", "LOW", "deadline", "Please finish the application by the posted closing date so it can enter the review queue."),
    ("LEGITIMATE", "LOW", "deadline", "The role remains open through the date listed on the official careers page."),
    ("LEGITIMATE", "LOW", "stage_id", "After you sign the written offer, upload your passport through the employer's secure onboarding portal."),
    ("LEGITIMATE", "LOW", "stage_id", "Following acceptance, the official HR portal will collect your Aadhaar document for employment records."),
    ("LEGITIMATE", "LOW", "stage_id", "For post-offer tax setup, enter PAN details in the secure company onboarding portal, not in this chat."),
    ("LEGITIMATE", "LOW", "stage_id", "The background check begins after the written offer. The verified screening portal explains which identity documents are needed."),
    ("LEGITIMATE", "LOW", "Once your contract is signed, submit right-to-work documents through the official employee portal."),
    ("LEGITIMATE", "LOW", "Payroll setup takes place after acceptance through the company's secure HR portal; no bank details are needed now."),
    ("LEGITIMATE", "LOW", "After signing the offer, add your account details to the approved payroll system to receive your stipend."),
    ("LEGITIMATE", "LOW", "The employer collects IFSC and account details only in its secure payroll portal after onboarding."),
    ("LEGITIMATE", "LOW", "PAN is not required for the application. Any tax paperwork happens after an offer in the official HR system."),
    ("LEGITIMATE", "LOW", "We never ask candidates to send an OTP, password, or account recovery code."),
    ("LEGITIMATE", "LOW", "There is no registration or interview fee. Candidates should not pay anyone for a selection."),
    ("LEGITIMATE", "LOW", "Training is provided after hiring and there is no deposit or equipment purchase required."),
    ("LEGITIMATE", "LOW", "The panel selected you after two interviews and a practical assessment. We will send a written offer for review."),
    ("LEGITIMATE", "LOW", "Congratulations on passing the final interview. HR will share the role terms through the candidate portal."),
    ("LEGITIMATE", "LOW", "Your interview is at 10:30 tomorrow. Please confirm by noon today so we can keep the room booking."),
    ("LEGITIMATE", "LOW", "Could you confirm your interview attendance by this evening? The calendar slot can be changed later."),
    ("LEGITIMATE", "LOW", "The interviewer needs to move our call. Please choose another time before the calendar invitation expires tomorrow."),
    ("LEGITIMATE", "LOW", "The stipend and start date are in the written offer. Payroll details are collected after you accept."),
    ("LEGITIMATE", "LOW", "A secure background-check form will arrive after the contract. Do not email identity documents to the recruiter."),
    ("LEGITIMATE", "LOW", "For security, verify the role on the employer's public careers page and never send identity numbers in a message."),
    ("LEGITIMATE", "LOW", "The onboarding checklist mentions PAN and bank details for later payroll setup; the recruiter does not need them now."),

    ("FRAUDULENT", "HIGH", "To reserve the internship, please pay the registration charge before the interview."),
    ("FRAUDULENT", "HIGH", "A refundable processing deposit is needed today to release your appointment letter."),
    ("FRAUDULENT", "HIGH", "The training fee must be transferred to the recruiter before you can start work."),
    ("FRAUDULENT", "HIGH", "Send the security deposit now or your selected position will be withdrawn."),
    ("FRAUDULENT", "HIGH", "Kindly share the one-time code from your phone so I can finish verifying your candidate profile."),
    ("FRAUDULENT", "HIGH", "For a smooth onboarding, please provide your account password and login code in this chat."),
    ("FRAUDULENT", "HIGH", "Before arranging an interview, send your bank account number and IFSC to this contact."),
    ("FRAUDULENT", "HIGH", "Please upload a photo of your Aadhaar card to this form before we discuss the role."),
    ("FRAUDULENT", "HIGH", "A PAN scan is needed by tonight to keep your offer active; there is no time to contact HR."),
    ("FRAUDULENT", "HIGH", "Could you send your passport image through this private chat right away? The job details follow later."),
    ("FRAUDULENT", "HIGH", "You are selected without an interview. A small placement fee will confirm your position."),
    ("FRAUDULENT", "HIGH", "Please keep the identity check confidential and send your national ID before the offer expires."),
    ("FRAUDULENT", "HIGH", "Payroll needs your bank details now. Do not contact the company's HR desk about this request."),
    ("FRAUDULENT", "HIGH", "To confirm tomorrow's interview, reply with the OTP sent to your phone."),
    ("FRAUDULENT", "HIGH", "The offer will be canceled unless you pay the verification charge within one hour."),
    ("FRAUDULENT", "MEDIUM", "Would you be comfortable completing an identity check through a form before we share the company name?"),
    ("FRAUDULENT", "MEDIUM", "The recruiter says your profile is shortlisted before an interview and asks you to continue on a private messenger."),
    ("FRAUDULENT", "MEDIUM", "Please keep this opening private and avoid contacting the employer until I send more information."),
    ("FRAUDULENT", "MEDIUM", "We can reserve a place for you if you confirm today, although the job posting is not yet available."),
    ("FRAUDULENT", "MEDIUM", "Before the first call, could you provide your complete date of birth and residential details on this unlisted form?"),
    ("FRAUDULENT", "MEDIUM", "Your profile has been chosen from a short review. Ask no questions until the formal letter is prepared."),
    ("FRAUDULENT", "MEDIUM", "A recruiter promises immediate selection after a brief chat but gives no interview or team details."),
    ("FRAUDULENT", "MEDIUM", "The sender says the role is confidential and asks you to reply tonight without checking the company site."),
    ("FRAUDULENT", "MEDIUM", "An early form requests your full legal details before explaining the position or hiring stages."),
    ("FRAUDULENT", "MEDIUM", "Please confirm interest within two hours; the recruiter says details about the employer will come afterward."),
    ("FRAUDULENT", "MEDIUM", "A message says the offer may disappear today and discourages calling the company to confirm it."),
    ("FRAUDULENT", "MEDIUM", "The recruiter asks you to keep the selection message secret while you wait for an unofficial form."),
    ("FRAUDULENT", "MEDIUM", "You are told you passed screening without a meeting and should act quickly to claim the opening."),
    ("FRAUDULENT", "MEDIUM", "The sender requests identity paperwork at the application stage but does not identify a secure employer portal."),
    ("FRAUDULENT", "MEDIUM", "A recruiter asks you to accept a role immediately and promises to explain the hiring process later."),
]

# A separate small validation set for deciding on context gates. These messages
# are not part of train.csv, test.csv, or the adversarial challenge set.
VALIDATION = [
    ("LOW", "A recruiter asks for my resume and a public portfolio before an interview."),
    ("LOW", "Please choose an interview time by tomorrow afternoon using the calendar link."),
    ("LOW", "Applications close next month on the date shown on the careers page."),
    ("LOW", "After accepting the written offer, upload your passport using the secure employee portal."),
    ("LOW", "The official payroll tool requests bank details after contract acceptance."),
    ("LOW", "We do not request identity documents during initial screening."),
    ("LOW", "The panel selected you after three interviews and a technical exercise."),
    ("LOW", "No application fee is charged and there is no equipment deposit."),
    ("LOW", "Please confirm today's interview by 4 pm so the room can be reserved."),
    ("LOW", "Your background check begins after you sign the offer in the candidate portal."),
    ("MEDIUM", "A recruiter asks for a PAN image before the first interview through an unknown form."),
    ("MEDIUM", "Your profile is shortlisted without a conversation; please verify the opening first."),
    ("MEDIUM", "The sender asks you to keep the role private until more details are shared."),
    ("MEDIUM", "Please confirm interest within two hours, before the company details are provided."),
    ("MEDIUM", "A recruiter says selection is nearly guaranteed before any assessment."),
    ("MEDIUM", "The message asks for personal details before naming the employer."),
    ("MEDIUM", "The offer may be withdrawn soon, but no document or payment is requested."),
    ("MEDIUM", "A recruiter delays sharing the public job description until after your response."),
    ("MEDIUM", "An identity check is requested early and there is no official portal link."),
    ("MEDIUM", "The sender moves the application to a private chat without a listed vacancy."),
    ("HIGH", "Please send your one-time code to activate the candidate account."),
    ("HIGH", "Pay the mandatory interview deposit before the appointment can be confirmed."),
    ("HIGH", "Upload your Aadhaar now or the offer will be canceled this evening."),
    ("HIGH", "Share your bank account and card details before the interview."),
    ("HIGH", "Send your password and keep this request secret from the company."),
    ("HIGH", "The processing fee is due in one hour; do not call HR to verify."),
    ("HIGH", "Reply with the verification code before your account is closed."),
    ("HIGH", "Provide your PAN document privately to reserve the role today."),
    ("HIGH", "The job is guaranteed without an interview after you transfer the training fee."),
    ("HIGH", "Share a passport scan and bank details before we release your offer."),
    ("LOW", "After signing the employment contract, complete identity setup in the official secure employee portal."),
    ("MEDIUM", "The official secure portal is ready after acceptance. Before your first interview, send your Aadhaar through this private chat."),
    ("HIGH", "After the contract is signed, send bank details by private chat before the interview or lose the offer."),
]


def write_csv(name: str, rows: list[tuple], fields: tuple[str, ...]) -> None:
    with (DATA / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)


def existing_messages(filename: str) -> list[str]:
    path = DATA / filename
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        return [row["text"] for row in csv.DictReader(stream)]


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    if len(CHALLENGE) != 60 or sum(label == "LEGITIMATE" for label, *_ in CHALLENGE) != 30:
        raise ValueError("Challenge set must have exactly 30 legitimate and 30 fraudulent messages")
    challenge_rows = []
    for index, row in enumerate(CHALLENGE, start=1):
        truth, risk, *content = row
        family, text = content if len(content) == 2 else (f"challenge_{index:02d}", content[0])
        challenge_rows.append((truth, risk, family, text))
    normalized = [" ".join(row[3].casefold().split()) for row in challenge_rows]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Duplicate challenge messages detected")
    held_messages = existing_messages("train.csv") + existing_messages("test.csv")
    validation_messages = [text for _, text in VALIDATION]
    for label, messages in (("challenge", [row[3] for row in challenge_rows]), ("validation", validation_messages)):
        for text in messages:
            normalized_text = " ".join(text.casefold().split())
            for previous in held_messages:
                ratio = SequenceMatcher(None, normalized_text, " ".join(previous.casefold().split())).ratio()
                if ratio >= 0.82:
                    raise ValueError(f"{label} example too similar to Phase 2 train/held-out text (similarity={ratio:.2f})")
        if label == "challenge":
            for text in messages:
                normalized_text = " ".join(text.casefold().split())
                for previous in validation_messages:
                    ratio = SequenceMatcher(None, normalized_text, " ".join(previous.casefold().split())).ratio()
                    if ratio >= 0.82:
                        raise ValueError(f"Challenge example too similar to validation text (similarity={ratio:.2f})")
    write_csv("adversarial_challenge.csv", challenge_rows, ("truth", "risk_label", "family", "text"))
    write_csv("validation.csv", [(label, text) for label, text in VALIDATION], ("risk_label", "text"))
    print(f"Wrote independent challenge={len(CHALLENGE)} (30 legitimate / 30 fraudulent), validation={len(VALIDATION)}.")


if __name__ == "__main__":
    main()
