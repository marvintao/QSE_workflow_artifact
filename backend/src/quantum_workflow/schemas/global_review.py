"""Schema for the global_review stage output: does the codegen code implement the original requirement?"""

from typing import Literal

from pydantic import BaseModel, Field


class GlobalReviewResult(BaseModel):
    """Verdict produced by the global-review agent between codegen and execute.

    verdict:
        approve - code implements the intent; proceed to execute.
        revise  - code diverges from the requirement; bounce back to
                  codegen with feedback.

    feedback: required when verdict is `revise`. Must tell codegen what
        to change in the next round at the code level (e.g. "change
        Q[i, i] to cost - input_div", not "improve the algorithm"). May
        be empty for `approve`.
    """

    verdict: Literal["approve", "revise"]
    feedback: str = Field(default="")
