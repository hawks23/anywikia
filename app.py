from extract_input import extract_entities
from extract_id import search_wikidata
import json

def main():
    inp = """
            The NVIDIA A100 is a 2020 data-center GPU built on the Ampere architecture, with 6,912 CUDA cores, 432 third-generation Tensor cores, and 40GB or 80GB of high-bandwidth memory. In 2026 it remains a mainstream choice for AI inference, fine-tuning, and mid-scale training. On the Akash marketplace, checked October 22, 2026, an 80GB A100 starts at $1.07/GPU-hr, averages $1.49/GPU-hr, with providers' top asking rate at $1.91/GPU-hr.

            TL;DR

            What it is: NVIDIA's Ampere-generation data-center GPU (GA100), launched 2020, still in heavy use in 2026.
            Headline specs: 6,912 CUDA cores, 432 Tensor cores, 40GB HBM2 or 80GB HBM2e, up to 2,039 GB/s bandwidth, 312 TFLOPS dense FP16.
            Variants: 40GB and 80GB, in PCIe or SXM form factors, plus the 8-GPU DGX A100 server.
            Where it sits: two generations behind NVIDIA's current Blackwell chips (B300/B200), but capable for most non-frontier AI work. The H100 delivers roughly 3 to 4 times its transformer throughput.
            Cost: on Akash, checked October 22, 2026, an 80GB A100 runs $1.07 to $1.91/GPU-hr, averaging $1.49/GPU-hr. See the FAQ and the pricing page for current rates.
            What is the NVIDIA A100?
            The NVIDIA A100 is a data-center GPU designed for AI training, inference, and high-performance computing (HPC). It launched in May 2020 as the first product built on NVIDIA's Ampere architecture, and an 80GB version followed in November 2020. It replaced the V100 (Volta) as NVIDIA's flagship accelerator and was itself succeeded by the H100 (Hopper) in 2022.

            The A100 introduced third-generation Tensor cores and the TF32 precision format, which sped up AI math without code changes, and it was the first NVIDIA GPU to support Multi-Instance GPU (MIG), which splits one physical card into isolated slices. In 2026 the A100 is no longer NVIDIA's fastest chip, but its mature software stack and wide availability keep it in active service for teams that do not need frontier-scale performance.
    """
    json_of_triples = json.dumps(extract_entities(inp)) # The whole list of every extracted entity

    

    #printing
    print(json_of_triples)

        # triples = search_wikidata(json_of_triples)


if __name__ == "__main__":
    main()