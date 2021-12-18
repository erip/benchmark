# Generated by gen_timm_models.py
import torch
import timm.models.resnest

from ...util.model import BenchmarkModel
from torchbenchmark.tasks import COMPUTER_VISION
from .config import TimmConfig

from torchbenchmark.util.framework.timm.args import parse_extraargs

class Model(BenchmarkModel):
    task = COMPUTER_VISION.CLASSIFICATION

    def __init__(self, device=None, jit=False,
                 variant='resnest14d', precision='float32',
                 eval_bs=32, train_bs=32, extra_args=[]):
        super().__init__()
        self.device = device
        self.jit = jit
        self.extra_args = parse_extraargs(extra_args)

        self.model = timm.create_model(variant, pretrained=False, scriptable=True)
        self.cfg = TimmConfig(model = self.model, device = device, precision = precision)
        self.example_inputs = self._gen_input(train_bs)
        self.model.to(
            device=self.device,
            dtype=self.cfg.model_dtype
        )

        # instantiate another model for inference
        self.eval_model = timm.create_model(variant, pretrained=False, scriptable=True)
        self.eval_model.eval()
        self.eval_model.to(
            device=self.device,
            dtype=self.cfg.model_dtype
        )
        self.eval_example_inputs = self._gen_input(eval_bs)
        if self.extra_args.fx2trt:
            assert self.device == 'cuda', "fx2trt is only available with CUDA."
            assert not self.jit, "fx2trt with JIT is not available."
            from torchbenchmark.util.fx2trt import lower_to_trt
            self.eval_model = lower_to_trt(module=self.eval_model, input=self.eval_example_inputs, \
                                           max_batch_size=eval_bs, fp16_mode=self.extra_args.eval_fp16)

        if jit:
            self.model = torch.jit.script(self.model)
            self.eval_model = torch.jit.script(self.eval_model)
            assert isinstance(self.eval_model, torch.jit.ScriptModule)
            self.eval_model = torch.jit.optimize_for_inference(self.eval_model)

    def _gen_input(self, batch_size):
        return torch.randn((batch_size,) + self.cfg.input_size, device=self.device, dtype=self.cfg.data_dtype)

    def _gen_target(self, batch_size):
        return torch.empty(
            (batch_size,) + self.cfg.target_shape,
            device=self.device, dtype=torch.long).random_(self.cfg.num_classes)

    def _step_train(self):
        self.cfg.optimizer.zero_grad()
        output = self.model(self.example_inputs)
        if isinstance(output, tuple):
            output = output[0]
        target = self._gen_target(output.shape[0])
        self.cfg.loss(output, target).backward()
        self.cfg.optimizer.step()

    # vision models have another model
    # instance for inference that has
    # already been optimized for inference
    def set_eval(self):
        pass

    def _step_eval(self):
        output = self.eval_model(self.eval_example_inputs)

    def get_module(self):
        self.example_inputs = self.example_inputs
        return self.model, (self.example_inputs,)

    def train(self, niter=1):
        self.model.train()
        self.example_inputs = self.example_inputs
        for _ in range(niter):
            self._step_train()

    def eval(self, niter=1):
        self.eval_model.eval()
        self.infer_example_inputs = self.infer_example_inputs
        with torch.no_grad():
            for _ in range(niter):
                self._step_eval()
